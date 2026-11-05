# MCP server profile: <APPLICATION NAME>

Fill this in once and keep it next to the tests. A person or an AI takes the context from here to write cases and run the battery. Everything specific to your application lives in this file and in `eval.config.json`.

## Server

- What a person can do with it, in one sentence: <…>
- Who uses it: <non-technical, technical, both>
- Transport: <stdio | HTTP>
- Local address: <http://localhost:PORT/mcp or command>
- Stage address: <https://…/mcp>
- Read-only or also writes: <…>
- Instructions size: <characters, and whether they fit in Claude Code's 4,096>
- Raised limit: <no | yes, with which value and where it is configured>

## Auth

- Model: <none | fixed token | OAuth with an external authorization server | own OAuth>
- How to get the test token: <command that issues a real token for the fixture user>
- Account isolation: <subdomain | header | parameter | none>
- Who the fixture user is: <…>

## Test data

- Where it comes from: <seed, anonymized snapshot, factory>
- How to reset the state: <before_case hook command>
- How to see the result after the run: <file, query, export; after_case hook command>
- Data that must never be used: <…>

## Vocabulary

- Words people use that the system names differently: <…>
- Real requests that have come in: <…>

## Goals

- Focus: <quality | cost | speed | balanced>
- Stop criteria: <clean ≥ 90%, zero silent failures>
- Budget per run: <US$ …>
- Budget per round: <US$ …>
- Acceptable call range: <…>

## Decisions

- Spike or fixture: <…>
- Models that must work: <…>
- What is left out on purpose: <…>
