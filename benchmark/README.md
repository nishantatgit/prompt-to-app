# Benchmark

Playwright tests for the 25 apps prompt-to-app must build.

## Structure

```
benchmark/
├── apps.json            the 25 prompts (id, slug, level, prompt)
├── deployments.json     live URL of each generated app
├── helpers/apps.ts      loads apps and URLs, builds tags
├── tests/
│   ├── common/          checks that run on every app
│   └── apps/            one file per app, e.g. 03-tip-calculator.spec.ts
└── results/
    ├── latest/          last run (not committed)
    └── week-01/         copied here when the weekly score is published
```

## Two kinds of tests

**Common** (`tests/common/common.spec.ts`), run for every deployed app:

- Page loads
- No console errors
- Fits a mobile screen

**Specific** (`tests/apps/NN-slug.spec.ts`), the pass check for one app.

An app **passes** only when all its common and specific tests pass.

## App contract

Tests find elements the way a user would, by label and text. So every generated app must:

- Give every input a visible label
- Give every button clear text

## Setup

```bash
yarn
yarn playwright install chromium
```

## Running

Put the app URL in `deployments.json`, or pass it as an environment variable:

```bash
APP_URL_3=https://my-tip-calculator.vercel.app yarn test
```

Filter with tags:

```bash
yarn test --grep @app03      # one app
yarn test --grep @level1     # one level
yarn test:common             # only common checks
yarn report                  # open the HTML report
```

Apps without a URL are skipped.
