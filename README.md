# VibeCheck: Verified Translation Validation Framework

VibeCheck is a post-hoc formal verification framework designed to produce a quantified, evidence-backed confidence score for whether LLM-generated Python workflow code adheres to its originating Business Process Model and Notation (BPMN) specification — not an absolute mathematical proof, but multiple independent verification techniques (structural, symbolic, dynamic, and process-equivalence) combined into a single certificate with a documented confidence level and known limitations.

By utilizing dynamic tracing, symbolic execution, and stuttering bisimulation, VibeCheck acts as a deterministic "auditor" to detect semantic flaws and logical hallucinations in AI-generated stateful workflows.

> **Current status**: module-by-module implementation status, architecture detail, and measured results live on the [project wiki](https://github.com/FYP-Epsilon/Vibe-Check/wiki) — start there for what's actually built and verified today, not just planned.

## 🏗️ System Architecture

The project is structured as a monorepo consisting of four decoupled, containerized modules:

* **`module_01_spec/` (Role A):** Parses BPMN 2.0 XML and extracts temporal logic properties (LTLf) with structural coverage guarantees.
* **`module_02_extract/` (Role B):** Utilizes Python's `ast` module and the Z3 Theorem Prover to translate LLM-generated Python scripts into a validated Workflow Intermediate Representation (WIR).
* **`module_03_equiv/` (Role C):** Lifts the JSON WIRs into formal C++ mathematical memory spaces using the SPOT library to compute process equivalence (stuttering bisimulation) and cluster AI implementations.
* **`module_04_ui/`:** A Streamlit web portal for driving the other three engines interactively — paste BPMN/code, see the certificate.

---

## 🚀 Getting Started

### Prerequisites

* [Docker](https://docs.docker.com/get-docker/) and Docker Compose
* Git

### 1. Clone the Repository

```bash
git clone https://github.com/FYP-Epsilon/Vibe-Check.git
cd Vibe-Check
```

### 2. Build and Run the Pipeline

We use Docker to ensure consistent environments across all modules (Python 3.10 for spec analysis, Python 3.11 for extraction and the UI portal, Ubuntu/C++ for formal model checking).

To build the images and run all engines simultaneously:

```bash
docker-compose up --build
```

> **Note:** Omit the `--build` flag on future runs unless you have modified a `Dockerfile` or `requirements.txt`.

### 🔍 Checking Logs & Debugging

When running `docker-compose up`, logs from all four containers will stream to your terminal.

If you want to view the logs for a specific module in isolation, open a new terminal and run:

* **Module 1:** `docker-compose logs -f spec-engine`
* **Module 2:** `docker-compose logs -f extract-engine`
* **Module 3:** `docker-compose logs -f equiv-engine`
* **Module 4:** `docker-compose logs -f ui-engine` — the only service exposed on a host port (`8501`); visit `http://localhost:8501` once it's up.

### 💻 Running an Interactive Shell

If you need to drop into a container to test a script or check dependencies manually:

```bash
docker-compose run --rm <container-name> bash
# Example: docker-compose run --rm equiv-engine bash
```

---

## 🤝 How to Contribute

Since this is a multi-module monorepo, strict version control is essential. Please follow these steps when contributing:

1. Ensure you are on the `main` branch and pull the latest changes:
   ```bash
   git pull origin main
   ```
2. Create a new branch following the naming conventions below.
3. Develop and test your module locally using Docker.
4. Commit your changes with clear, descriptive commit messages.
5. Push your branch to GitHub and open a Pull Request (PR) against `main`.
6. Request a review from your team members before merging.

### Branch Naming Conventions

To keep our repository organized, please prefix your branch names with the type of work and the module you are working on:

**Format:** `<type>/<module>/<short-description>`

**Types:**

* `feat/` — New features or core logic
* `fix/` — Bug fixes
* `docs/` — Changes to documentation or README
* `refactor/` — Code restructuring without changing behavior

**Examples:**

* `feat/mod1/xml-parser`
* `fix/mod2/z3-timeout`
* `feat/mod3/spot-lts-lift`
* `docs/root/update-readme`

---

## 📄 License

This project is licensed under the GNU General Public License v3.0 (GPLv3). See the [LICENSE](LICENSE) file for details.
