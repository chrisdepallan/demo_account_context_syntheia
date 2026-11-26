# Contributing

This repo is a sample corpus for testing an MCP documentation server on a larger repository. It mixes Markdown docs, Python code, tests and reports about one fictional product, Acme Cloud. The goal of every change is the same: keep the corpus realistic, consistent and safe to index.

## What is the one rule that matters most?

Every business value (a price, a limit, a duration, an ID format) is defined once, in `docs/reference/constants-and-glossary.md`. Code, tests, docs and reports repeat those values but never invent a different one. If you change a value:

1. Change it in `docs/reference/constants-and-glossary.md` first.
2. Search the repo for the old value and update every place that uses it.
3. Run the tests.
4. Update the expected answers in `eval/test-questions.md`.

Releases and incidents work the same way: `docs/reference/release-and-incident-index.md` is the index, and `CHANGELOG.md`, `reports/releases/` and `reports/incidents/` must agree with it.

## How do I write a doc page?

1. One topic per `##` heading. Phrase the heading the way a user asks, for example "## How do I invite a member?". The indexer splits files at headings, so each section must make sense on its own.
2. Write menu paths in bold with arrows, for example **Settings → Billing → Invoices**.
3. Put concrete values in the text, not only in a table. Add a sentence under a table that states its main point.
4. Refer to people by role ("the Owner", "the on-call engineer"), not by name.
5. End the file with `Last reviewed: <date>`.

## How do I write code and tests?

- Python 3.10 or later, standard library only. Tests use pytest.
- Each package under `src/acme_cloud/` depends on `common` and on `accounts/plans.py`. Packages do not import each other's services; they take optional `notifier` and `audit` collaborators instead.
- Never call `datetime.now()` in a service. Take a `Clock` so tests can move time.
- Put the business rule and its numbers in the module docstring and in named constants. The docstrings are indexed as documentation.
- Each module has a test file in `tests/unit/<package>/`. Flows that cross packages go in `tests/integration/`.

Run the tests from the repo root:

```text
python -m pip install pytest
python -m pytest
```

Check the size of the corpus:

```text
python tools/repo_stats.py --headings
```

## What must never be committed?

- Secrets of any kind. API keys in examples must be obviously fake, such as `acme_test_EXAMPLEEXAMPLEEXAMPLEEXAMPLE0000`.
- Real customer or personal data. Use `@example.com` addresses and the fictional `*.acme-cloud.example` URLs.
- Card numbers, national identity numbers, passport or driving licence numbers, or health records. This includes fake or "test" values. Payment methods appear only as opaque tokens such as `pm_9XK2M4QH7T`.

The indexer's secret filter only skips files by name. Anything pasted into a Markdown or Python file is indexed.

## What do I do after merging?

There is no auto-sync. Re-index the library after merging to `main`, then run the questions in `eval/test-questions.md` against the assistant and compare with the expected answers.

Last reviewed: 2026-11-26
