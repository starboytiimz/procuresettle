#!/usr/bin/env python3
"""Prove joint cancellation and remaining-value refund on a local Stellar ledger.

Requires Stellar CLI 28.1.0, a healthy protocol-28 standalone `local` network,
three funded identities in a private config directory, and an SAC holding at
least 100 base units for the buyer. No Testnet or Mainnet calls are made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import tomllib

EXPECTED_WASM_SIZE = 25_484
EXPECTED_WASM_SHA = "78b5c6dec22ad1cea497223ff411af544dcd1e9fd613b85514f2c5ae03873a7c"
TX_HASH = re.compile(r"Signing transaction:\s*([0-9a-fA-F]{64})")
CONTRACT_ID = re.compile(r"\bC[A-Z2-7]{55}\b")
LINES = [
    {"line_id": 1, "ordered_quantity": 10, "unit_price": "6"},
    {"line_id": 2, "ordered_quantity": 8, "unit_price": "5"},
]


class Proof:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo = Path(__file__).resolve().parents[1]
        self.config = args.config_dir.resolve()
        self.wasm = args.wasm.resolve()
        self.report_dir = args.report_dir.resolve()
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.report_dir / "local-cancellation-proof.txt"
        self.log = self.log_path.open("w", encoding="utf-8")
        self.cli = ["stellar", "--config-dir", str(self.config)]
        self.transactions: list[dict[str, str]] = []

    def close(self) -> None:
        self.log.close()

    def run(
        self,
        args: list[str],
        *,
        expected_success: bool = True,
        expected_error: str | None = None,
        read_only: bool = False,
    ) -> tuple[str, str, list[str]]:
        cmd = self.cli + args
        display = shlex.join(cmd).replace(str(self.config), "$PRIVATE_CONFIG_DIR")
        self.log.write(f"\n$ {display}\n")
        try:
            proc = subprocess.run(
                cmd, text=True, capture_output=True, check=False, timeout=180
            )
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            self.log.write(f"TIMEOUT after 180s\nSTDOUT:\n{out}\nSTDERR:\n{err}\n")
            self.log.flush()
            raise RuntimeError(f"command timed out; inspect {self.log_path}") from exc
        self.log.write(
            f"EXIT={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}\n"
        )
        self.log.flush()
        output = proc.stdout + "\n" + proc.stderr
        if expected_success and proc.returncode != 0:
            raise RuntimeError(f"command exited {proc.returncode}; inspect {self.log_path}")
        if not expected_success:
            if proc.returncode == 0:
                raise RuntimeError("unauthorized cancellation unexpectedly succeeded")
            if expected_error and expected_error.casefold() not in output.casefold():
                raise RuntimeError(
                    f"expected error marker {expected_error!r} was absent; inspect {self.log_path}"
                )
        hashes = TX_HASH.findall(output)
        for tx_hash in hashes:
            result = self.fetch_result(tx_hash)
            succeeded = '"tx_success"' in result
            self.transactions.append({"hash": tx_hash.lower(), "outcome": "tx_success" if succeeded else "tx_failed"})
            if expected_success and not succeeded:
                raise RuntimeError(f"submitted transaction {tx_hash} did not report tx_success")
            if not expected_success and succeeded:
                raise RuntimeError(f"rejected cancellation produced successful transaction {tx_hash}")
        if expected_success and not read_only and not hashes:
            raise RuntimeError(f"mutating command produced no transaction hash; inspect {self.log_path}")
        return proc.stdout, proc.stderr, hashes

    def fetch_result(self, tx_hash: str) -> str:
        cmd = self.cli + ["tx", "fetch", "result", "--hash", tx_hash, "--network", "local"]
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=180)
        output = proc.stdout + ("\nSTDERR:\n" + proc.stderr if proc.stderr else "")
        self.log.write(
            f"\n$ stellar tx fetch result --hash {tx_hash} --network local\n"
            f"EXIT={proc.returncode}\n{output}\n"
        )
        self.log.flush()
        if proc.returncode != 0:
            raise RuntimeError(f"could not fetch local transaction result {tx_hash}: {output}")
        return proc.stdout

    def invoke(
        self,
        contract: str,
        source: str,
        method: str,
        *args: str,
        signers: tuple[str, ...] = (),
        expected_success: bool = True,
        expected_error: str | None = None,
        read_only: bool = False,
    ) -> tuple[Any, str]:
        if method == "cancel_po" and signers:
            value, output = self.submit_cancellation(
                contract,
                source,
                *args,
                authorize_supplier=True,
            )
            return value, output
        command = [
            "contract", "invoke", "--contract-id", contract,
            "--source-account", source, "--network", "local",
        ]
        for signer in signers:
            command += ["--sign-with-key", signer]
        if signers:
            command.append("--auto-sign")
        command += ["--", method, *args]
        out, err, _ = self.run(
            command,
            expected_success=expected_success,
            expected_error=expected_error,
            read_only=read_only,
        )
        if not expected_success:
            return None, out + "\n" + err
        return self.json_value(out, err), out + "\n" + err

    def submit_cancellation(
        self,
        contract: str,
        source: str,
        *cancel_args: str,
        authorize_supplier: bool,
    ) -> tuple[str, str]:
        """Build, simulate, authorize, and submit one cancellation transaction.

        The Stellar CLI exposes only the transaction source signer on contract
        invoke. Soroban address authorization entries are signed here using the
        pinned stellar-sdk helper so each party signs the exact simulated call.
        """
        from stellar_sdk import Keypair, SorobanServer, TransactionEnvelope
        import stellar_sdk
        from stellar_sdk.address import Address
        from stellar_sdk.auth import authorize_entry
        from stellar_sdk import scval, xdr as stellar_xdr
        from stellar_sdk.soroban_rpc import AuthMode

        if stellar_sdk.__version__ != "13.1.0":
            raise RuntimeError(f"expected stellar-sdk 13.1.0, got {stellar_sdk.__version__}")

        command = [
            "contract", "invoke", "--contract-id", contract,
            "--source-account", source, "--network", "local", "--build-only",
            "--", "cancel_po", *cancel_args,
        ]
        transaction_xdr, err, _ = self.run(command, read_only=True)
        envelope = TransactionEnvelope.from_xdr(
            transaction_xdr.strip(), "Standalone Network ; February 2017"
        )
        buyer_phrase = tomllib.loads(
            (self.config / "identity" / f"{self.args.buyer_identity}.toml").read_text()
        )["seed_phrase"]
        supplier_phrase = tomllib.loads(
            (self.config / "identity" / f"{self.args.supplier_identity}.toml").read_text()
        )["seed_phrase"]
        buyer_key = Keypair.from_mnemonic_phrase(buyer_phrase)
        supplier_key = Keypair.from_mnemonic_phrase(supplier_phrase)
        if buyer_key.public_key != self.address(self.args.buyer_identity):
            raise RuntimeError("buyer identity seed does not match configured public key")
        if supplier_key.public_key != self.address(self.args.supplier_identity):
            raise RuntimeError("supplier identity seed does not match configured public key")

        server = SorobanServer("http://localhost:8000/soroban/rpc")
        try:
            simulation = server.simulate_transaction(
                envelope, auth_mode=AuthMode.RECORD_ALL_NOROOT
            )
            if simulation.error:
                raise RuntimeError(f"cancellation simulation failed: {simulation.error}")
            prepared = server.prepare_transaction(envelope, simulation)
            operation = prepared.transaction.operations[0]
            entries = operation.auth
            if not entries:
                raise RuntimeError("simulation returned no cancellation auth entries")
            latest = server.get_latest_ledger().sequence
            keys_by_address = {
                buyer_key.public_key: buyer_key,
                supplier_key.public_key: supplier_key,
            }
            signed_entries = []
            found_supplier = False
            found_buyer = False
            for entry in entries:
                if entry.credentials.address is None:
                    if entry.credentials.type.name == "SOROBAN_CREDENTIALS_SOURCE_ACCOUNT":
                        found_buyer = True
                        signed_entries.append(entry)
                        continue
                    raise RuntimeError(
                        f"unsupported cancellation auth credential type {entry.credentials.type}"
                    )
                address = Address.from_xdr_sc_address(
                    entry.credentials.address.address
                ).address
                key = keys_by_address.get(address)
                if key is None:
                    raise RuntimeError(f"unexpected cancellation authorizer {address}")
                if address == buyer_key.public_key:
                    found_buyer = True
                if address == supplier_key.public_key:
                    found_supplier = True
                if authorize_supplier or address != supplier_key.public_key:
                    entry = authorize_entry(
                        entry,
                        key,
                        latest + 100,
                        "Standalone Network ; February 2017",
                    )
                signed_entries.append(entry)
            if not found_supplier:
                raise RuntimeError("simulation did not require supplier authorization")
            operation.auth = signed_entries
            prepared.sign(buyer_key)
            tx_hash = prepared.hash_hex()
            self.log.write(
                f"\nSDK sendTransaction hash={tx_hash} "
                f"supplier_authorized={authorize_supplier}\n"
            )
            self.log.flush()
            send_result = server.send_transaction(prepared)
            if send_result.status.value != "PENDING":
                raise RuntimeError(
                    f"cancellation transaction was not accepted for ledger execution: "
                    f"status={send_result.status} error={send_result.error_result_xdr}"
                )
            result = server.poll_transaction(tx_hash, max_attempts=30)
            succeeded = result.status.value == "SUCCESS"
            self.log.write(
                f"SDK getTransaction hash={tx_hash} status={result.status.value} "
                f"result_xdr={result.result_xdr}\n"
            )
            self.log.flush()
            expected = authorize_supplier
            self.transactions.append({
                "hash": tx_hash,
                "outcome": "tx_success" if succeeded else "tx_failed",
            })
            if succeeded != expected:
                raise RuntimeError(
                    f"cancellation tx {tx_hash} status {result.status.value}; expected "
                    f"{'SUCCESS' if expected else 'FAILED'}"
                )
            authorization_detail = ""
            if not succeeded:
                if not result.result_meta_xdr:
                    raise RuntimeError(
                        f"failed cancellation {tx_hash} has no result metadata to verify authorization"
                    )
                result_meta = stellar_xdr.TransactionMeta.from_xdr(result.result_meta_xdr)
                diagnostic_events = (
                    result_meta.v4.diagnostic_events
                    if result_meta.v == 4 and result_meta.v4 is not None
                    else []
                )
                supplier_auth_rejected = False
                for diagnostic in diagnostic_events or []:
                    body = diagnostic.event.body.v0 if diagnostic.event.body else None
                    if body is None:
                        continue
                    data = scval.to_native(body.data)
                    if (
                        isinstance(data, list)
                        and data
                        and data[0] == "failed account authentication with error"
                        and any(
                            isinstance(item, Address)
                            and item.address == supplier_key.public_key
                            for item in data
                        )
                    ):
                        supplier_auth_rejected = True
                        break
                if not supplier_auth_rejected:
                    raise RuntimeError(
                        f"failed cancellation {tx_hash} did not record rejected supplier authorization"
                    )
                authorization_detail = (
                    f"supplier authorization rejected for {supplier_key.public_key}"
                )
            fetch = self.fetch_result(tx_hash)
            if succeeded and '"tx_success"' not in fetch:
                raise RuntimeError(f"CLI fetch did not confirm successful cancellation {tx_hash}")
            if not succeeded and '"tx_failed"' not in fetch:
                raise RuntimeError(f"CLI fetch did not confirm failed cancellation {tx_hash}")
            return tx_hash, (
                f"tx_hash={tx_hash} status={result.status.value} "
                f"{authorization_detail} "
                f"error_result={result.result_xdr if not succeeded else 'none'}"
            )
        finally:
            server.close()

    @staticmethod
    def json_value(stdout: str, stderr: str = "") -> Any:
        for text in (stdout, stderr):
            for line in reversed(text.splitlines()):
                try:
                    return json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
        raise RuntimeError(f"CLI returned no JSON value: {stdout!r} {stderr!r}")

    def query(self, contract: str, method: str, *args: str) -> Any:
        value, _ = self.invoke(
            contract, self.args.buyer_identity, method, *args, read_only=True
        )
        return value

    def balance(self, address: str) -> int:
        out, err, _ = self.run(
            ["token", "balance", "--id", self.args.sac_id, "--account", address, "--network", "local"],
            read_only=True,
        )
        for line in reversed((out + "\n" + err).splitlines()):
            try:
                return int(line.strip())
            except ValueError:
                continue
        raise RuntimeError(f"CLI returned no raw token balance: {out!r} {err!r}")

    def address(self, identity: str) -> str:
        out, err, _ = self.run(["keys", "public-key", identity], read_only=True)
        matches = re.findall(r"\bG[A-Z2-7]{55}\b", out + "\n" + err)
        if not matches:
            raise RuntimeError(f"could not resolve public key for {identity}")
        return matches[-1]

    def deploy(self) -> str:
        out, err, _ = self.run([
            "contract", "deploy", "--wasm", str(self.wasm),
            "--source-account", self.args.issuer_identity, "--network", "local",
        ])
        matches = CONTRACT_ID.findall(out + "\n" + err)
        if not matches:
            raise RuntimeError("deployment returned no contract ID")
        return matches[-1]

    def run_proof(self) -> dict[str, Any]:
        size = self.wasm.stat().st_size
        wasm_sha = hashlib.sha256(self.wasm.read_bytes()).hexdigest()
        if size != EXPECTED_WASM_SIZE or wasm_sha != EXPECTED_WASM_SHA:
            raise RuntimeError(f"unexpected WASM size/hash: {size}/{wasm_sha}")

        cli_version, _, _ = self.run(["--version"], read_only=True)
        if not cli_version.split() or cli_version.split()[1] != "28.1.0":
            raise RuntimeError(f"expected Stellar CLI 28.1.0, got {cli_version.strip()!r}")
        network, network_err, _ = self.run(["network", "info", "--network", "local"], read_only=True)
        network_info = network + network_err
        if "Standalone Network ; February 2017" not in network_info or "Protocol Version: 28" not in network_info:
            raise RuntimeError("expected a protocol-28 standalone local network")

        buyer = self.address(self.args.buyer_identity)
        supplier = self.address(self.args.supplier_identity)
        if buyer != self.args.buyer_address or supplier != self.args.supplier_address:
            raise RuntimeError("configured identity addresses do not match the supplied addresses")
        initial = {
            "buyer": self.balance(buyer),
            "supplier": self.balance(supplier),
        }
        if initial["buyer"] < 100:
            raise RuntimeError("buyer SAC balance must be at least 100 base units")

        contract = self.deploy()
        po_id = time.time_ns() // 1_000_000
        lines_arg = json.dumps(LINES, separators=(",", ":"))
        self.invoke(
            contract, self.args.buyer_identity, "create_po",
            "--po_id", str(po_id), "--buyer", buyer, "--supplier", supplier,
            "--token", self.args.sac_id, "--lines", lines_arg,
        )
        created = self.query(contract, "get_po", "--po_id", str(po_id))
        if created.get("status") != "Draft" or int(created.get("total_value", -1)) != 100:
            raise RuntimeError(f"created PO terms differ from expected 100: {created!r}")

        self.invoke(contract, self.args.supplier_identity, "accept_po", "--po_id", str(po_id))
        self.invoke(contract, self.args.buyer_identity, "fund_po", "--po_id", str(po_id))
        funded = self.query(contract, "get_po", "--po_id", str(po_id))
        if funded.get("status") != "Funded" or int(funded.get("funded_value", -1)) != 100:
            raise RuntimeError(f"PO did not reach fully funded state: {funded!r}")

        receipt_lines = json.dumps(
            [{"line_id": 1, "quantity_delta": 6}, {"line_id": 2, "quantity_delta": 4}],
            separators=(",", ":"),
        )
        self.invoke(
            contract, self.args.supplier_identity, "submit_receipt",
            "--po_id", str(po_id), "--receipt_id", "1", "--quantities", receipt_lines,
        )
        paid_value, _ = self.invoke(
            contract, self.args.buyer_identity, "accept_receipt_and_settle",
            "--po_id", str(po_id), "--receipt_id", "1",
        )
        if int(paid_value) != 56:
            raise RuntimeError(f"partial receipt settled {paid_value!r}, expected 56")
        after_settlement = {
            "po": self.query(contract, "get_po", "--po_id", str(po_id)),
            "line_1": self.query(contract, "get_line", "--po_id", str(po_id), "--line_id", "1"),
            "line_2": self.query(contract, "get_line", "--po_id", str(po_id), "--line_id", "2"),
            "buyer": self.balance(buyer),
            "supplier": self.balance(supplier),
            "contract": self.balance(contract),
        }
        if (
            after_settlement["po"].get("status") != "Funded"
            or int(after_settlement["po"].get("paid_value", -1)) != 56
            or after_settlement["line_1"].get("accepted_quantity") != 6
            or after_settlement["line_2"].get("accepted_quantity") != 4
            or after_settlement["buyer"] != initial["buyer"] - 100
            or after_settlement["supplier"] != initial["supplier"] + 56
            or after_settlement["contract"] != 44
        ):
            raise RuntimeError(f"partial settlement state/balances differ: {after_settlement!r}")

        unauthorized_before = {
            "po": self.query(contract, "get_po", "--po_id", str(po_id)),
            "buyer": self.balance(buyer),
            "supplier": self.balance(supplier),
            "contract": self.balance(contract),
        }
        _, unauthorized_output = self.submit_cancellation(
            contract,
            self.args.buyer_identity,
            "--po_id", str(po_id),
            authorize_supplier=False,
        )
        unauthorized_after = {
            "po": self.query(contract, "get_po", "--po_id", str(po_id)),
            "buyer": self.balance(buyer),
            "supplier": self.balance(supplier),
            "contract": self.balance(contract),
        }
        if unauthorized_before != unauthorized_after:
            raise RuntimeError("one-party cancellation changed PO state or balances")

        self.invoke(
            contract, self.args.buyer_identity, "cancel_po", "--po_id", str(po_id),
            signers=(self.args.supplier_identity,),
        )
        final = {
            "po": self.query(contract, "get_po", "--po_id", str(po_id)),
            "buyer": self.balance(buyer),
            "supplier": self.balance(supplier),
            "contract": self.balance(contract),
        }
        expected = {
            "status": "Cancelled", "funded_value": 100,
            "paid_value": 56, "refunded_value": 44,
            "buyer_balance": initial["buyer"] - 56,
            "supplier_balance": initial["supplier"] + 56,
            "contract_balance": 0,
        }
        actual = {
            "status": final["po"].get("status"),
            "funded_value": int(final["po"].get("funded_value", -1)),
            "paid_value": int(final["po"].get("paid_value", -1)),
            "refunded_value": int(final["po"].get("refunded_value", -1)),
            "buyer_balance": final["buyer"],
            "supplier_balance": final["supplier"],
            "contract_balance": final["contract"],
        }
        if actual != expected:
            raise RuntimeError(f"final cancellation state differs: {actual!r} != {expected!r}")

        return {
            "verdict": "PASS",
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=self.repo,
                check=True, text=True, capture_output=True,
            ).stdout.strip(),
            "wasm_size": size,
            "wasm_sha256": wasm_sha,
            "stellar_cli": cli_version.strip(),
            "stellar_sdk": "13.1.0",
            "network": network_info.strip(),
            "contract_id": contract,
            "po_id": po_id,
            "initial_balances": initial,
            "partial_settlement": after_settlement,
            "unauthorized_cancellation_rejected": True,
            "unauthorized_output": unauthorized_output,
            "unauthorized_before_after_equal": True,
            "final_state": final,
            "expected_final_economic_state": expected,
            "transaction_results": self.transactions,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, required=True)
    parser.add_argument("--wasm", type=Path, default=Path("target/wasm32v1-none/release/procuresettle.wasm"))
    parser.add_argument("--report-dir", type=Path, default=Path(".codex/reports/cancellation"))
    parser.add_argument("--issuer-identity", required=True)
    parser.add_argument("--buyer-identity", required=True)
    parser.add_argument("--supplier-identity", required=True)
    parser.add_argument("--buyer-address", required=True)
    parser.add_argument("--supplier-address", required=True)
    parser.add_argument("--sac-id", required=True)
    args = parser.parse_args()
    proof = Proof(args)
    try:
        summary = proof.run_proof()
        proof.log.write("\nCANCELLATION_PROOF_SUMMARY_JSON:\n")
        proof.log.write(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        proof.log.flush()
        print("PROCURESETTLE_LOCAL_CANCELLATION_PROOF_SUMMARY")
        print(json.dumps({**summary, "report": str(proof.log_path)}, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"LOCAL_CANCELLATION_PROOF_FAILED: {exc}", file=sys.stderr)
        print(f"Raw log: {proof.log_path}", file=sys.stderr)
        return 1
    finally:
        proof.close()


if __name__ == "__main__":
    raise SystemExit(main())
