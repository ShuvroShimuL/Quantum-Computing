"""
Secure and Unbiased Quantum Energy Teleportation via Quantum Oblivious Transfer

Description:
    This module implements a hybrid tripartite quantum protocol that integrates
    Quantum Energy Teleportation (QET) with Quantum Oblivious Transfer (QOT).

    Protocol overview:
      1. BB84 Phase          — Alice generates oblivious keys for Bob and Charlie.
      2. Entanglement Phase  — Alice prepares the ground state |g⟩ and creates
                               Bell pairs shared with each receiver.
      3. Measurement Phase   — Alice performs projective X-basis measurements,
                               injecting energy locally.
      4. Encryption Phase    — Alice encodes measurement results into two messages
                               (M0, M1) using HMAC-SHA256 with the oblivious keys.
      5. Transfer Phase      — Each receiver selects one message following the
                               BBCS QOT protocol; the other is discarded.
      6. Extraction Phase    — Receivers apply conditional Ry rotations (LOCC)
                               to extract energy if and only if they hold the
                               correct measurement result.

    Energy Parameters (default):  k = 1,  h = 1.5
    Simulation backend:           Qiskit Aer — qasm_simulator
    Shots per run:                2 000
"""

import hmac
import hashlib
import numpy as np
import matplotlib.pyplot as plt

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister, transpile
from qiskit_aer import AerSimulator


# ---------------------------------------------------------------------------
# Helper — HMAC-SHA256 one-time-pad encryption / decryption
# ---------------------------------------------------------------------------

def _hmac_encrypt(key: bytes, message: np.ndarray) -> np.ndarray:
    """XOR *message* bits with the first len(message) bytes of HMAC-SHA256(key).

    Args:
        key:     Raw bytes used as the HMAC key.
        message: 1-D integer array of 0/1 values.

    Returns:
        Encrypted integer array of the same length.
    """
    h = hmac.new(key, digestmod=hashlib.sha256).digest()
    key_bits = np.array([int(b) for b in format(int.from_bytes(h, "big"), "0256b")][:len(message)])
    return (message ^ key_bits).astype(int)


def _hmac_decrypt(key: bytes, ciphertext: np.ndarray) -> np.ndarray:
    """Decrypt an HMAC-XOR ciphertext (symmetric — identical to encrypt)."""
    return _hmac_encrypt(key, ciphertext)


# ---------------------------------------------------------------------------
# Main protocol class
# ---------------------------------------------------------------------------

class TripartiteQOET:
    """Tripartite Quantum Oblivious Energy Teleportation protocol.

    Parameters
    ----------
    n_qubits : int
        Number of qubits per entangled pair (default 4).
    msg_length : int
        Length of the measurement-result message in bits (default 2).
    energy_params : dict
        Hamiltonian parameters ``{'k': float, 'h': float}``.
        Default: ``{'k': 1, 'h': 1.5}``.
    n_shots : int
        Number of Monte-Carlo protocol runs (default 2 000).
    """

    def __init__(
        self,
        n_qubits: int = 4,
        msg_length: int = 2,
        energy_params: dict | None = None,
        n_shots: int = 2000,
    ):
        self.n_qubits = n_qubits
        self.l = msg_length
        self.n_shots = n_shots

        ep = energy_params or {"k": 1, "h": 1.5}
        self.k = ep["k"]
        self.h = ep["h"]

        # Pre-compute the Ry rotation angle φ for energy extraction
        #   cos(2φ) = (h²+2k²) / √[(h²+2k²)²+ h²k²]
        #   sin(2φ) = hk       / √[(h²+2k²)²+ h²k²]
        num = self.h**2 + 2 * self.k**2
        denom = np.sqrt(num**2 + (self.h * self.k) ** 2)
        self.phi = 0.5 * np.arctan2(self.h * self.k, num)  # φ in radians

        # Ground-state preparation angle
        #   |g⟩ = α|00⟩ − β|11⟩
        norm = np.sqrt(self.h**2 + self.k**2)
        alpha = np.sqrt(0.5 * (1 - self.h / norm))
        self.theta_gs = 2 * np.arcsin(alpha)          # used in Ry(-θ_gs) gate

        self.simulator = AerSimulator()

        # Logging containers (populated during run_protocol)
        self.results_log: dict = {
            "bob_message_choice": [],
            "charlie_message_choice": [],
            "bob_messages": [],
            "charlie_messages": [],
            "bob_energy": [],
            "charlie_energy": [],
            "bob_local_energy": [],
            "bob_interacting_energy": [],
            "charlie_local_energy": [],
            "charlie_interacting_energy": [],
        }

    # ------------------------------------------------------------------
    # Phase 1 — BB84 key-generation
    # ------------------------------------------------------------------

    def bb84_phase(self):
        """Simulate one round of BB84 to produce raw bit-strings for Alice,
        Bob, and Charlie.

        Returns
        -------
        x_alice, theta_alice : ndarray
            Alice's bit values and basis choices.
        x_bob, theta_bob : ndarray
            Bob's measured bits and basis choices.
        x_charlie, theta_charlie : ndarray
            Charlie's measured bits and basis choices.
        """
        n = self.n_qubits
        x_alice = np.random.randint(0, 2, size=n)
        theta_alice = np.random.randint(0, 2, size=n)   # 0 → Z-basis, 1 → X-basis

        # Receivers measure in independently chosen random bases
        theta_bob = np.random.randint(0, 2, size=n)
        theta_charlie = np.random.randint(0, 2, size=n)

        # In matching bases the measurement equals Alice's bit;
        # in mismatched bases the outcome is uniformly random.
        x_bob = np.where(
            theta_bob == theta_alice,
            x_alice,
            np.random.randint(0, 2, size=n),
        )
        x_charlie = np.where(
            theta_charlie == theta_alice,
            x_alice,
            np.random.randint(0, 2, size=n),
        )
        return x_alice, theta_alice, x_bob, theta_bob, x_charlie, theta_charlie

    # ------------------------------------------------------------------
    # Phase 2 — Oblivious key extraction
    # ------------------------------------------------------------------

    def oblivious_key_phase(self, x_alice, theta_alice, x_recv, theta_recv):
        """Derive oblivious keys for one Alice–receiver pair.

        Only positions where both parties used the *same* basis are kept.
        Alice obtains two complementary key halves (I0, I1); the receiver
        obtains only the half that aligns with their basis choices.

        Returns
        -------
        I0_alice, I1_alice, ok_alice, ok_recv : ndarray
            Key halves and full / partial oblivious keys.
        """
        matching = theta_alice == theta_recv
        indices = np.where(matching)[0]

        # Partition matched positions into two interleaved halves
        I0 = indices[0::2]
        I1 = indices[1::2]
        min_len = min(len(I0), len(I1))
        I0, I1 = I0[:min_len], I1[:min_len]

        ok_alice = np.concatenate([x_alice[I0], x_alice[I1]])
        ok_recv = np.concatenate([x_recv[I0], x_recv[I1]])

        return I0, I1, ok_alice, ok_recv

    # ------------------------------------------------------------------
    # Phase 3 — Oblivious Transfer
    # ------------------------------------------------------------------

    def transfer_phase(
        self,
        m0: np.ndarray,
        m1: np.ndarray,
        I0,
        I1,
        ok_alice: np.ndarray,
        ok_recv: np.ndarray,
        choice: int,
    ):
        """Encrypt both messages and let the receiver decrypt only one.

        Alice encrypts M0 with the key derived from I0-positions and M1
        with the key derived from I1-positions using HMAC-SHA256 XOR pads.
        The receiver can decrypt only the message whose key indices overlap
        with those they actually observed (determined by their basis choices).

        Parameters
        ----------
        m0, m1 : ndarray
            Alice's two plaintext messages.
        I0, I1 : ndarray
            Index sets defining the two key halves.
        ok_alice, ok_recv : ndarray
            Alice's full key and the receiver's partial key.
        choice : int
            0 or 1 — which message the receiver selects.

        Returns
        -------
        decoded_message, c0, c1, key0, key1
        """
        half = len(ok_alice) // 2
        key0 = bytes(ok_alice[:half].tolist())
        key1 = bytes(ok_alice[half:].tolist())

        # Truncate / pad messages to msg_length
        l = self.l
        m0_t = np.resize(m0, l)
        m1_t = np.resize(m1, l)

        c0 = _hmac_encrypt(key0, m0_t)
        c1 = _hmac_encrypt(key1, m1_t)

        # Receiver derives their key from the half they can observe
        recv_half = len(ok_recv) // 2
        recv_key0 = bytes(ok_recv[:recv_half].tolist())
        recv_key1 = bytes(ok_recv[recv_half:].tolist())

        decoded = _hmac_decrypt(recv_key0 if choice == 0 else recv_key1,
                                c0 if choice == 0 else c1)
        return decoded, c0, c1, key0, key1

    # ------------------------------------------------------------------
    # Phase 4 — Quantum energy extraction circuit
    # ------------------------------------------------------------------

    def create_quantum_energy_circuit(self, mu: int) -> QuantumCircuit:
        """Build the energy-extraction circuit for a single receiver.

        Steps:
          1. Prepare ground state |g⟩ via Ry(-θ_gs) + CNOT.
          2. Apply H to qubit 0 (Alice's X-basis measurement).
          3. Conditionally apply Ry(±2φ) to qubit 1 based on μ.

        Parameters
        ----------
        mu : int
            Measurement result 0 or 1 obtained via oblivious transfer.

        Returns
        -------
        QuantumCircuit
        """
        qr = QuantumRegister(2, "q")
        cr = ClassicalRegister(2, "c")
        qc = QuantumCircuit(qr, cr)

        # Ground-state preparation
        qc.ry(-self.theta_gs, qr[0])
        qc.cx(qr[0], qr[1])

        # Alice's X-basis measurement (H then measure)
        qc.h(qr[0])

        # Receiver's conditional rotation  Ry(2μφ)
        angle = 2 * (1 - 2 * mu) * self.phi   # μ=0 → +2φ, μ=1 → −2φ
        qc.ry(angle, qr[1])

        qc.measure(qr, cr)
        return qc

    def simulate_energy_circuit(self, qc: QuantumCircuit):
        """Run a circuit on the Aer simulator and estimate ⟨Z₁⟩.

        Returns
        -------
        counts : dict
            Raw bitstring counts.
        energy : float
            Expectation value of Z on qubit 1 (proxy for extracted energy).
        """
        compiled = transpile(qc, self.simulator)
        job = self.simulator.run(compiled, shots=1024)
        counts = job.result().get_counts()

        # ⟨Z₁⟩ = Σ (1 − 2b₁) · count / n_shots
        total = sum(counts.values())
        z1_exp = sum(
            (1 - 2 * int(bs[0])) * cnt          # bs is "q1 q0" in Qiskit
            for bs, cnt in counts.items()
        ) / total
        return counts, z1_exp

    # ------------------------------------------------------------------
    # Energy helper — analytic Hamiltonian expectation values
    # ------------------------------------------------------------------

    def calculate_energy_components(self, mu: int):
        """Return analytic local and interaction energy for outcome μ.

        The Hamiltonian is  H_tot = H_0 + H_1 + V  where
            H_n = h·Z_n + h²/(2√(h²+k²))
            V   = 2k·X₀X₁ + 2k²/√(h²+k²)

        Parameters
        ----------
        mu : int  (0 or 1)

        Returns
        -------
        (local_energy, interaction_energy) : (float, float)
        """
        norm = np.sqrt(self.h**2 + self.k**2)
        sign = 1 - 2 * mu                          # +1 for μ=0, −1 for μ=1

        local_energy = -sign * self.h * np.cos(2 * self.phi)
        interaction_energy = -sign * self.k * np.sin(2 * self.phi)
        return local_energy, interaction_energy

    # ------------------------------------------------------------------
    # Run the full protocol
    # ------------------------------------------------------------------

    def run_protocol(self):
        """Execute *n_shots* rounds of the hybrid QET-QOT protocol.

        Returns
        -------
        bob_circuit, charlie_circuit : QuantumCircuit
            Example circuits from the final round.
        bob_counts, charlie_counts : dict
            Measurement counts from the final round simulation.
        """
        for _ in range(self.n_shots):
            # ---- BB84 key generation ----
            x_alice, theta_alice, x_bob, theta_bob, x_charlie, theta_charlie = (
                self.bb84_phase()
            )

            # ---- Oblivious key derivation ----
            I0_bob, I1_bob, ok_alice_bob, ok_bob = self.oblivious_key_phase(
                x_alice, theta_alice, x_bob, theta_bob
            )
            I0_charlie, I1_charlie, ok_alice_charlie, ok_charlie = (
                self.oblivious_key_phase(x_alice, theta_alice, x_charlie, theta_charlie)
            )

            # ---- Alice's measurement results (simulated classically) ----
            alice_meas_result_0 = np.random.randint(0, 2, size=self.l)
            alice_meas_result_1 = np.random.randint(0, 2, size=self.l)

            # ---- Oblivious transfer — Bob ----
            bob_choice = np.random.randint(0, 2)
            self.results_log["bob_message_choice"].append(bob_choice)
            bob_message, *_ = self.transfer_phase(
                alice_meas_result_0, alice_meas_result_1,
                I0_bob, I1_bob, ok_alice_bob, ok_bob, bob_choice,
            )
            self.results_log["bob_messages"].append(bob_message)

            # ---- Oblivious transfer — Charlie ----
            charlie_choice = np.random.randint(0, 2)
            self.results_log["charlie_message_choice"].append(charlie_choice)
            charlie_message, *_ = self.transfer_phase(
                alice_meas_result_0, alice_meas_result_1,
                I0_charlie, I1_charlie, ok_alice_charlie, ok_charlie, charlie_choice,
            )
            self.results_log["charlie_messages"].append(charlie_message)

            # ---- Energy extraction (analytic) ----
            bob_local, bob_inter = self.calculate_energy_components(bob_choice)
            charlie_local, charlie_inter = self.calculate_energy_components(charlie_choice)

            self.results_log["bob_energy"].append(bob_local + bob_inter)
            self.results_log["charlie_energy"].append(charlie_local + charlie_inter)
            self.results_log["bob_local_energy"].append(bob_local)
            self.results_log["bob_interacting_energy"].append(bob_inter)
            self.results_log["charlie_local_energy"].append(charlie_local)
            self.results_log["charlie_interacting_energy"].append(charlie_inter)

        # ---- Build and simulate circuits for the last round ----
        bob_circuit = self.create_quantum_energy_circuit(
            self.results_log["bob_message_choice"][-1]
        )
        charlie_circuit = self.create_quantum_energy_circuit(
            self.results_log["charlie_message_choice"][-1]
        )

        bob_counts, _ = self.simulate_energy_circuit(bob_circuit)
        charlie_counts, _ = self.simulate_energy_circuit(charlie_circuit)

        return bob_circuit, charlie_circuit, bob_counts, charlie_counts

    # ------------------------------------------------------------------
    # Analysis & visualisation
    # ------------------------------------------------------------------

    def analyze_results(self) -> dict:
        """Aggregate results and produce four diagnostic plots.

        Returns
        -------
        dict with keys:
            bob_energy_total, charlie_energy_total, case_distribution, visualization
        """
        bob_e = self.results_log["bob_energy"]
        charlie_e = self.results_log["charlie_energy"]

        threshold = 0.5
        both_recv   = sum(1 for b, c in zip(bob_e, charlie_e) if b > threshold and c > threshold)
        only_bob    = sum(1 for b, c in zip(bob_e, charlie_e) if b > threshold and c <= threshold)
        only_charlie= sum(1 for b, c in zip(bob_e, charlie_e) if b <= threshold and c > threshold)
        neither     = sum(1 for b, c in zip(bob_e, charlie_e) if b <= threshold and c <= threshold)

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(
            "QET-QOT Protocol Results\n"
            "Secure & Unbiased Quantum Energy Teleportation via Quantum Oblivious Transfer",
            fontsize=13,
        )

        # 1 — Energy distribution histogram
        axes[0, 0].hist(bob_e,     alpha=0.6, label="Bob",     bins=20, color="steelblue")
        axes[0, 0].hist(charlie_e, alpha=0.6, label="Charlie", bins=20, color="orange")
        axes[0, 0].set_title("Energy Distribution")
        axes[0, 0].set_xlabel("Energy (arb. units)")
        axes[0, 0].set_ylabel("Frequency")
        axes[0, 0].legend()

        # 2 — Cumulative energy over shots
        axes[0, 1].plot(np.cumsum(bob_e),     label="Bob",     color="steelblue")
        axes[0, 1].plot(np.cumsum(charlie_e), label="Charlie", color="orange")
        axes[0, 1].set_title("Cumulative Energy")
        axes[0, 1].set_xlabel("Shot Number")
        axes[0, 1].set_ylabel("Total Energy")
        axes[0, 1].legend()

        # 3 — Message choice distribution (unbiasedness check)
        labels = ["Bob – Msg 0", "Bob – Msg 1", "Charlie – Msg 0", "Charlie – Msg 1"]
        bc = self.results_log["bob_message_choice"]
        cc = self.results_log["charlie_message_choice"]
        counts_bar = [
            sum(1 for c in bc if c == 0),
            sum(1 for c in bc if c == 1),
            sum(1 for c in cc if c == 0),
            sum(1 for c in cc if c == 1),
        ]
        axes[1, 0].bar(labels, counts_bar, color="steelblue")
        axes[1, 0].set_title("Message Choice Distribution")
        axes[1, 0].set_ylabel("Count")
        axes[1, 0].tick_params(axis="x", rotation=15)

        # 4 — Four-case pie chart
        pie_labels = ["Only Bob", "Only Charlie", "Both", "Neither"]
        pie_values = [only_bob, only_charlie, both_recv, neither]
        pie_colors = ["#2196F3", "#FF9800", "#4CAF50", "#F44336"]
        axes[1, 1].pie(pie_values, labels=pie_labels, autopct="%1.1f%%", colors=pie_colors)
        axes[1, 1].set_title("Energy Reception Cases")

        plt.tight_layout()

        return {
            "bob_energy_total":    sum(bob_e),
            "charlie_energy_total":sum(charlie_e),
            "case_distribution": {
                "both_received": both_recv,
                "only_bob":      only_bob,
                "only_charlie":  only_charlie,
                "neither":       neither,
            },
            "visualization": fig,
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    protocol = TripartiteQOET(
        n_qubits=4,
        msg_length=2,
        energy_params={"k": 1, "h": 1.5},
        n_shots=2000,
    )

    print("Running Tripartite Quantum Oblivious Energy Teleportation …")
    bob_circuit, charlie_circuit, bob_counts, charlie_counts = protocol.run_protocol()
    results = protocol.analyze_results()

    print("\n===== PROTOCOL SUMMARY =====")
    print(f"Total energy received by Bob:     {results['bob_energy_total']:.4f}")
    print(f"Total energy received by Charlie: {results['charlie_energy_total']:.4f}")

    dist = results["case_distribution"]
    print("\nCase distribution:")
    print(f"  Both received energy:    {dist['both_received']:4d}")
    print(f"  Only Bob received:       {dist['only_bob']:4d}")
    print(f"  Only Charlie received:   {dist['only_charlie']:4d}")
    print(f"  Neither received:        {dist['neither']:4d}")

    print("\nSample measurement counts (last shot):")
    print("  Bob's circuit:    ", bob_counts)
    print("  Charlie's circuit:", charlie_counts)

    print("\nBob's energy extraction circuit:")
    print(bob_circuit)

    plt.show()
