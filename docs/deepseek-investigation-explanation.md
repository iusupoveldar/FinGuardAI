# How DeepSeek supports an account investigation

## Short answer

DeepSeek does **not** decide whether an account or customer is fraudulent. It
does not calculate the operational risk score or assign the risk band. Those
values are produced before DeepSeek is called by the versioned local risk model.

DeepSeek's role is to turn an existing customer risk snapshot, transaction
evidence, and retrieved internal policy passages into a structured explanation
for a human investigator. The explanation highlights risk factors, connects
them to known transaction IDs, cites relevant policy sources, suggests next
review steps, and states limitations. A human reviewer remains responsible for
the final account disposition.

The application stores the **validated, normalized explanation** in PostgreSQL
and reuses it for the same versioned investigation snapshot. It does not store
the unvalidated raw response string returned by DeepSeek.

## End-to-end decision-support flow

```text
Account transactions
        |
        v
Local feature builder and risk model
        |
        |  customer score, band, top transactions, factual drivers
        v
Persisted risk snapshot
        |
        +--------------------+
        |                    |
        v                    v
Local policy retrieval    Bounded investigation packet
        |                    |
        +---------+----------+
                  |
                  v
          DeepSeek explanation
                  |
                  v
       Schema and safety validation
                  |
          +-------+-------+
          |               |
       valid           invalid/error
          |               |
          v               v
 Validated narrative   Deterministic narrative
          |               |
          +-------+-------+
                  |
                  v
       Persisted investigation result
                  |
                  v
        Human review and disposition
```

### 1. The local model calculates the priority

The scoring pipeline builds transaction features and produces a probability for
each recent transaction. It also calculates a transparent rule benchmark. The
customer-level operational priority combines the highest transaction
probability, the mean of the three highest probabilities, and the maximum rule
score. The result is converted to a score from 0 to 100 and a `low`, `medium`,
or `high` band.

Transactions are connected to the customers who own the sending and receiving
accounts, so this is currently a **customer-level investigation priority**, even
when a customer owns multiple accounts. The score is explicitly described as
an operational priority, not a probability of guilt.

The persisted risk snapshot includes:

- the score and risk band;
- the scoring cutoff step;
- model and feature versions;
- up to three notable transactions from the scoring process;
- plain-language transaction facts and detected patterns.

Implementation: [`ml/score.py`](../ml/score.py) and
[`ml/risk_model.py`](../ml/risk_model.py).

### 2. Local retrieval selects applicable policy context

The policy retriever turns the saved risk factors and patterns into a search
query against the local Chroma policy index. It filters and ranks active policy
passages, applies jurisdiction and token limits, and returns no more than five
passages to the investigation packet.

This retrieval step gives DeepSeek relevant internal guidance without asking
the language model to invent policy. Implementation:
[`ai/retrieval.py`](../ai/retrieval.py).

### 3. The application builds a bounded packet

The packet sent to DeepSeek contains the already-calculated score and band,
model versions, factual risk drivers, no more than five notable transactions,
and no more than five retrieved policy passages. Transaction evidence and
policy passages are labelled as data, not instructions.

DeepSeek is instructed to:

- use only facts, evidence IDs, and source IDs in the packet;
- leave the supplied numeric score unchanged;
- avoid claiming that fraud is proven;
- avoid inventing transactions, policies, thresholds, or customer attributes;
- state when evidence is insufficient;
- return a JSON object matching the required schema.

The packet is deliberately compact and does not add customer profile fields.
It does include the customer reference used by the application.

Implementation: [`ai/prompts.py`](../ai/prompts.py).

### 4. DeepSeek creates the explanation, not the decision

When generation is enabled and the policy context, API key, pricing, and budget
are available, DeepSeek returns these narrative sections:

- `summary`;
- `risk_factors`, with one or more supplied evidence IDs per factor;
- `relevant_rules`, with one or more supplied policy source IDs per rule;
- `recommended_next_steps`;
- `limitations`;
- `sources`.

These fields help an investigator understand why the customer was prioritized
and what to inspect next. They do not authorize blocking an account, filing a
report, or concluding that fraud occurred. The current investigation model
does not contain a human outcome or disposition field, so final reviewer
decisions are not yet recorded by this workflow.

The DeepSeek request is stateless, JSON-only, non-streaming, and has thinking
disabled. Implementation: [`ai/deepseek.py`](../ai/deepseek.py).

### 5. The response must pass application validation

Before anything returned by DeepSeek is saved as the investigation narrative,
the application:

1. Parses the response as JSON and validates its exact schema and size limits.
2. Rejects risk factors that cite transaction evidence outside the packet.
3. Rejects rules that cite policy sources outside the packet.
4. Rejects specified prohibited fraud conclusions.
5. Discards source metadata echoed by the model and reconstructs it from the
   trusted policy passages supplied by the application.

If validation fails, or DeepSeek is disabled, unavailable, over budget, or has
no usable policy passages, the investigation receives a deterministic narrative
derived from the same score and evidence. The persisted risk score does not
change because DeepSeek fails.

## Is the DeepSeek response cached or stored?

Yes, with an important distinction between the application cache and
DeepSeek's prompt-token cache.

### Application-level persisted investigation

The application's "cache" is a durable row in the PostgreSQL `investigations`
table, not a temporary in-memory cache. After successful validation, the
structured narrative is serialized into `investigations.evidence.result`.
The narrative summary is also copied to `investigations.summary` for compact
history responses.

The following data is persisted:

| Data | Storage location | Notes |
| --- | --- | --- |
| Validated summary | `investigations.summary` | Also present inside the structured result. |
| Validated narrative | `investigations.evidence.result` | Includes factors, rules, next steps, limitations, and canonical sources. |
| Risk snapshot | `investigations.evidence.risk_snapshot` | Freezes the score, band, evidence, cutoff, and versions used. |
| Retrieved policy passages | `investigations.evidence.policy_sources` | Includes the passages used to build the packet. |
| Generation origin | `investigations.evidence.generation_mode` | Either `deepseek` or `deterministic_fallback`. |
| Fallback explanation | `investigations.evidence.fallback_reason` | `null` for a valid DeepSeek result. |
| Usage and cost telemetry | `investigations.evidence.token_usage` | Model, tokens, cache-token counts, latency, retries, and estimated cost. |
| Raw DeepSeek response string | Not stored | It is parsed, validated, and normalized before persistence. |
| Hidden chain-of-thought | Not requested or stored | Thinking is disabled in the API request. |

Implementation: [`backend/app/models/investigation.py`](../backend/app/models/investigation.py)
and
[`backend/app/services/investigation_service.py`](../backend/app/services/investigation_service.py).

### How application reuse works

When `POST /investigate/{customer_id}` is called, the application calculates a
snapshot key from:

- customer ID;
- transaction cutoff step;
- risk-model version;
- feature version;
- policy-corpus version;
- prompt version;
- configured DeepSeek model.

If an investigation with that key already exists, the API returns the existing
row and normally does not call DeepSeek again. This makes repeat requests
idempotent and lets the frontend retrieve completed work through:

- `GET /investigations/{investigation_id}`;
- `GET /customers/{customer_id}/investigations/latest`;
- `GET /investigations/` for compact history.

A changed cutoff or version produces a different key and therefore a new
investigation. One current caveat is that the key does not hash the contents of
the risk evidence itself. If a risk row is updated in place while all key fields
remain unchanged, an already-completed investigation can still be reused.

Implementation: [`backend/app/api/investigation.py`](../backend/app/api/investigation.py)
and
[`backend/app/services/investigation_service.py`](../backend/app/services/investigation_service.py).

### DeepSeek prompt-token caching

The DeepSeek API may report `prompt_cache_hit_tokens` and
`prompt_cache_miss_tokens`. The application records those counts to calculate
and audit request cost. These metrics refer to reuse of prompt input tokens by
the provider; they are separate from the PostgreSQL investigation cache and do
not indicate that the generated response was saved as an application cache
entry by DeepSeek.

The application does not implement its own provider-response cache. Its reuse
mechanism is the persisted, validated investigation row described above.

## Practical interpretation for an investigator

Treat the output as an evidence-grounded briefing:

- The **risk model** says how urgently the customer should be reviewed.
- The **retriever** supplies potentially relevant internal policy passages.
- **DeepSeek** organizes those inputs into a readable explanation and review
  checklist.
- The **validator** prevents unsupported IDs, malformed output, and specified
  prohibited conclusions from becoming the saved narrative.
- The **human investigator** verifies the underlying records and owns the final
  disposition.

DeepSeek can improve consistency and readability, but it is neither the source
of the score nor the final decision-maker.
