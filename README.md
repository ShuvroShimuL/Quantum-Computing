# Secure and Unbiased Quantum Energy Teleportation via Quantum Oblivious Transfer

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Qiskit](https://img.shields.io/badge/Qiskit-1.4.2-6929C4?logo=IBM)](https://qiskit.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Authors

| Name |
|---|
| Shamimul Shimul |
| Sara Rahman |
| Tahmina Sultana |

**Supervisor:** Dr. Mahdy Rahman Chowdhury, Associate Professor, ECE Department, NSU

---

## Overview

This project designs, implements, and experimentally validates a **hybrid tripartite quantum protocol** that merges two foundational quantum information primitives:

| Protocol | What it does |
|---|---|
| **Quantum Energy Teleportation (QET)** | Transfers energy between physically separated quantum systems via entanglement and Local Operations + Classical Communication (LOCC), without physically moving any energy carrier. |
| **Quantum Oblivious Transfer (QOT)** | Lets Alice send two messages to a receiver such that the receiver obtains exactly one, and Alice learns nothing about which one was chosen. |

### The Problem This Solves

Standard QET protocols have two critical weaknesses:

1. **No security** — the classical channel carrying Alice's measurement results is unprotected and vulnerable to interception.
2. **Sender bias** — Alice can deterministically choose which receiver extracts energy, making fair multi-party distribution impossible.

By integrating QOT into QET, this work eliminates both issues simultaneously.

---

## Protocol Description

The protocol involves three parties: **Alice** (energy sender), **Bob** (receiver 1), and **Charlie** (receiver 2).

```
┌─────────────────────────────────────────────────────────────────────┐
│                     6-Phase Hybrid QET-QOT Protocol                 │
├────────────┬────────────────────────────────────────────────────────┤
│  Phase 1   │  BB84 Key Generation                                   │
│            │  Alice ↔ Bob and Alice ↔ Charlie independently.        │
│            │  Bases are compared; matching positions form the       │
│            │  oblivious key.                                        │
├────────────┼────────────────────────────────────────────────────────┤
│  Phase 2   │  Entanglement Preparation                              │
│            │  Alice prepares ground state |g⟩ via Ry + CNOT gates   │
│            │  and creates Bell pairs |Φ+⟩ shared with each receiver.│
├────────────┼────────────────────────────────────────────────────────┤
│  Phase 3   │  Alice's Projective Measurement                        │
│            │  Alice measures in the X-basis, injecting energy       │
│            │  locally. Results μ_B, μ_C ∈ {+1, -1}.                 │
├────────────┼────────────────────────────────────────────────────────┤
│  Phase 4   │  Message Encryption (HMAC-SHA256 XOR pad)              │
│            │  Alice encodes μ into two messages M0 (correct) and    │
│            │  M1 (incorrect), encrypted with the two halves of      │
│            │  the oblivious key.                                    │
├────────────┼────────────────────────────────────────────────────────┤
│  Phase 5   │  Oblivious Transfer (BBCS protocol)                    │
│            │  Each receiver chooses one message. They can decrypt   │
│            │  only the message whose key half they possess. Alice   │
│            │  never learns the choice.                              │
├────────────┼────────────────────────────────────────────────────────┤
│  Phase 6   │  Conditional Energy Extraction                         │
│            │  Receivers apply Ry(2μφ) rotations. Correct μ enables  │
│            │  energy extraction; incorrect μ yields nothing.        │
└────────────┴────────────────────────────────────────────────────────┘
```

### Key Equations

**Hamiltonian:**

$$H_{\text{tot}} = H_0 + H_1 + V, \quad H_n = hZ_n + \frac{h^2}{2\sqrt{h^2+k^2}}, \quad V = 2kX_0X_1 + \frac{2k^2}{\sqrt{h^2+k^2}}$$

**Ground state:**

$$|g\rangle = \sqrt{\tfrac{1}{2}\!\left(1 - \frac{h}{\sqrt{h^2+k^2}}\right)}|00\rangle - \sqrt{\tfrac{1}{2}\!\left(1 + \frac{h}{\sqrt{h^2+k^2}}\right)}|11\rangle$$

**Conditional operator for energy extraction:**

$$U(\mu) = R_y(2\mu\phi), \quad \cos(2\phi) = \frac{h^2+2k^2}{\sqrt{(h^2+2k^2)^2+h^2k^2}}, \quad \sin(2\phi) = \frac{hk}{\sqrt{(h^2+2k^2)^2+h^2k^2}}$$

---

## Results

Simulation parameters: `k = 1`, `h = 1.5`, `n_shots = 2000`, backend: **Qiskit Aer qasm_simulator**

| Metric | Value |
|---|---|
| Both receivers extract energy | **~51.5%** of trials |
| Only Bob extracts | ~15.4% |
| Only Charlie extracts | ~16.9% |
| Neither extracts | ~16.2% |
| Bias between Bob & Charlie | Not statistically significant |
| Max probability of guessing correct message | ≤ 50% (QOT guarantee) |

The near-equal cumulative energy curves for Bob and Charlie across 2 000 shots confirm the protocol's **unbiasedness**.

---

## Repository Structure

```
QET-QOT/
├── notebooks/
│   └── QET_QOT_Protocol.ipynb   # Clean, fully documented Jupyter notebook
├── src/
│   └── qet_qot_protocol.py      # Standalone Python module (importable)
├── docs/
│   └── (place the project report PDF here)
├── results/
│   └── (generated plots saved here)
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/QET-QOT.git
cd QET-QOT
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4a. Run as a script

```bash
python src/qet_qot_protocol.py
```

### 4b. Run the notebook

```bash
jupyter notebook notebooks/QET_QOT_Protocol.ipynb
```

### 4c. Import in your own code

```python
from src.qet_qot_protocol import TripartiteQOET

protocol = TripartiteQOET(
    n_qubits=4,
    msg_length=2,
    energy_params={'k': 1, 'h': 1.5},
    n_shots=2000,
)

bob_circuit, charlie_circuit, bob_counts, charlie_counts = protocol.run_protocol()
results = protocol.analyze_results()

print(f"Bob total energy:     {results['bob_energy_total']:.4f}")
print(f"Charlie total energy: {results['charlie_energy_total']:.4f}")
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `qiskit` | 1.4.2 | Quantum circuit design & compilation |
| `qiskit-aer` | ≥ 0.14 | Qasm simulator backend |
| `numpy` | ≥ 1.24 | Numerical computation, BB84 simulation |
| `matplotlib` | ≥ 3.7 | Result visualisation |
| `hmac`, `hashlib` | stdlib | HMAC-SHA256 one-time-pad encryption |

---

## Limitations

- **Noise-free simulation** — the current implementation runs on an ideal simulator. Real IBM hardware introduces decoherence (amplitude damping, depolarizing noise) that degrades fidelity.
- **Two receivers only** — multi-party scalability (N > 2) requires further theoretical and engineering work.
- **Classical channel** — while QOT secures the message choice, the classical channel itself still relies on standard cryptographic assumptions.
- **Energy efficiency** — extracted energy is bounded by the energy invested in preparing entangled states; net transfer efficiency remains low.

---

## Future Work

- Noise-resilient validation using Qiskit's `NoiseModel` and real IBM backends
- Quantum error correction tailored to QET operations
- Extension to N-party oblivious energy distribution
- Integration with Quantum Key Distribution (QKD) for fully quantum-secure classical channels
- Hardware-specific optimisations for superconducting, trapped-ion, and photonic platforms

---

## References

1. M. Hotta, *Quantum energy teleportation with cold atoms*, Phys. Rev. A **80**, 042323 (2009)
2. M. Ikeda et al., *Experimental demonstration of quantum energy teleportation on a superconducting quantum processor*, npj Quantum Inf. **8**, 117 (2022)
3. C. Santos, P. Mateus, A. Pinto, *A review of quantum oblivious transfer protocols*, Quantum Inf. Process **18**, 32 (2019)
4. C. H. Bennett, G. Brassard, C. Crépeau, M.-H. Skubiszewska, *Practical quantum oblivious transfer*, Journal of Cryptology **5**, 3–28 (1992)
5. S. Wehner, D. Elkouss, R. Hanson, *Quantum internet: A vision for the road ahead*, Science **362** (2018)
6. W. K. Wootters and W. H. Zurek, *A single quantum cannot be cloned*, Nature **299**, 802–803 (1982)
7. R. Horodecki et al., *Quantum entanglement*, Rev. Mod. Phys. **81**, 865–942 (2009)

---

## License

This project is released under the [MIT License](LICENSE).  
© 2025 Shamimul Shimul, Sara Rahman, Tahmina Sultana — North South University
