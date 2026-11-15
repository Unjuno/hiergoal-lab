# HierGoal Lab — Real Hermes Agent Research

An Apache-2.0 research harness for observing a **real Hermes Agent** repairing a Python package while explicitly planning long-, mid-, and short-term subgoals.

**Status: scaffold ready for local execution; no paid model benchmark has been run or published.**

**Scope:** one observational case study; **no baseline/comparison condition**, no performance improvement claim, and no reproduction of H-JEPA's neural architecture.

## Quick start (macOS / Linux / WSL2)

Requires Git, Python 3.11+ for the harness, and Hermes Agent installed separately.

~~~bash
git clone https://github.com/Unjuno/hiergoal-lab.git
cd hiergoal-lab

# First verify code without spending any API credit
python3 -m unittest discover -s tests -v
python3 scripts/run_hermes.py --dry-run

# After installing/configuring Hermes and the OpenAI API key:
hermes doctor
python3 scripts/run_hermes.py --model gpt-6-luna --reasoning low --max-turns 20
~~~

If Hermes is not installed, follow the [official installation instructions](https://hermes-agent.nousresearch.com/docs/getting-started/installation). On macOS / Linux / WSL2 the official CLI installer command is:

~~~bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
~~~

Examine third-party install scripts before executing them; do not run the installer as root unnecessarily. Once installed, use the **interactive** command below to configure the direct OpenAI API provider and existing API key:

~~~bash
hermes model
~~~

Select **OpenAI API (direct)**, not ChatGPT subscription/Codex OAuth or OpenRouter. The experiment explicitly passes the provider "openai-api" and model "gpt-6-luna"; if your account cannot access that model, the run should fail and its diagnostics will be recorded. The official [OpenAI model catalog](https://developers.openai.com/api/docs/models/gpt-6-luna) lists the model.

**Never paste your key into a GitHub file, issue, run log, or chat.** If already configured under Hermes, you do not need to configure it again. The runner uses the normal Hermes credential resolution.

## Experiment

One test fixture is copied to a fresh directory. Hermes must create a three-horizon RESEARCH_PLAN.md, edit real Python files, run visible tests, and revise affected subgoals when needed. A separate deterministic grader is executed after Hermes returns.

The harness invokes Hermes with:

- provider: openai-api
- model: gpt-6-luna (override possible)
- reasoning: low (override possible)
- toolsets: file,terminal,todo only
- ignore-user-config and ignore-rules to reduce unrelated interference
- query-file and stream-json for an auditable invocation
- max-turns: 20, timeout: 900 seconds

These settings do **not** guarantee cost or host-security isolation. The agent is given local shell/file tools. Run in a disposable VM/container or low-privilege account with no sensitive files, repositories, production credentials, or writable important mounts. A copied working directory is not a security sandbox. Killing the CLI may not stop an already-running gateway turn; check the Hermes session afterward.

**Outputs are kept locally and gitignored**:

~~~text
runs/ledger-release-<UTC>-<id>/
  workspace/               actual changed project + RESEARCH_PLAN.md
  query.txt                exact submitted prompt
  invocation.json          exact CLI arguments (no API key)
  hermes.stream.jsonl      raw stream events
  hermes.stderr.log        diagnostics
  pretest.log              verification that fixture was initially broken
  visible_tests.log        final public tests
  independent_tests.log    final outside-workspace grader
  changes.diff             source code diff
  summary.json             completion verdict + measured counts
~~~

The result has a **PASS / FAIL / UNCERTAIN** status. Successful CLI exit alone does not count as software-task completion. Planning is scored separately: existence of three labels in a file is **not** evidence that Hermes actually obeyed the plan. Inspect the trace and the artifact manually.

### API expenses

The OpenAI catalog currently lists standard short-context GPT-6 Luna at **$0.10 per million input tokens**, **$0.50 per million output tokens**. Costs depend on caching, context length, service tier, auxiliary calls and other usage. The summary's USD estimate uses only the visible Hermes result token counts; it is **not** a billing receipt or a hard budget cap. Manage project spend in the OpenAI Platform console. Do a single task first; do not run batches automatically.

Official pricing: https://developers.openai.com/api/docs/models/gpt-6-luna

## Reproducibility and citations

- Detailed protocol (Japanese): [docs/protocol_ja.md](docs/protocol_ja.md)
- Original Hermes feature proposal: https://github.com/NousResearch/hermes-agent/issues/156054
- Research motivation: Zhang et al., H-JEPA: End-to-End Learning of Hierarchical World Models for Visual Planning, https://arxiv.org/abs/2610.06805
- Hermes CLI stream-json reference: https://hermes-agent.nousresearch.com/docs/reference/cli-commands

This repository is independently authored and licensed Apache-2.0; Hermes Agent is a separately licensed upstream dependency, and neither Nous Research nor OpenAI endorses these results. No claimed causal improvement is warranted by one observed run.

**Do not publish raw traces without inspecting/redacting them**: tool output can contain data from your local system. After the first real experiment, review summary.json and changes.diff, then publish sanitized results and link them to the upstream Issue.
