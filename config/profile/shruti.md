# Shruti Kukreja — Master Profile / Answer Bank

> **Purpose:** single source of truth for job applications. `/prep` reads this file to draft
> application answers and tailor the resume. Keep it updated by hand — everything downstream
> is only as good as this file.
>
> **Convention:** lines marked `<!-- TODO -->` need your decision. Anything in a
> `copy-paste` block is meant to be pasted into a form verbatim.

---

## 1. Identity & logistics (exact ATS field values)

| Field | Value |
|---|---|
| Full name | Shruti Kukreja |
| First / Last | Shruti / Kukreja |
| Email (use on all applications) | shrutikukreja8@gmail.com |
| Phone | +91 98211 68775 |
| Location | Delhi, India |
| LinkedIn | https://linkedin.com/in/shruti-kukreja |
| GitHub | https://github.com/ShrutiKukreja |
| Portfolio / website | <!-- TODO: add if you build one, else leave blank --> |
| Current employer | PwC India |
| Current title | Senior Consultant, Advisory — AI Products |
| Total experience | 8+ years (since Aug 2017) |
| AI/ML product experience | 3 years (production AI systems) |

### Work authorisation — answer these consistently

| Question as asked on forms | Your answer |
|---|---|
| Are you legally authorised to work in the US? | **No** |
| Will you now or in future require visa sponsorship (US)? | **Yes** |
| Authorised to work in India? | **Yes** |
| Authorised to work in UK / EU? | **No** — sponsorship required |
| Open to relocation? | **Yes** |
| Open to in-office / hybrid (25%+)? | **Yes** |
| Preferred locations | India, US, UK, EU, Middle East, North East, or fully remote |

> **Strategy note:** for US frontier labs (OpenAI, Anthropic, Google DeepMind, xAI), sponsorship
> is the single biggest filter. Prioritise (a) their India/London/Dublin/Zurich offices,
> (b) explicitly remote reqs, (c) India-based AI companies and EU labs with established
> relocation programmes. Do not lie on the sponsorship question — it is verified and it
> voids offers.

### Logistics

| Field | Value |
|---|---|
| Notice period | 90 days |
| Earliest start date | "90-day notice, negotiable to ~60 days" |
| Current CTC | 20,00,000 LPA |
| Expected CTC (India) | 50,00,000 LPA |
| Expected comp (US, USD) | 200,000 USD |
| Expected comp (EU, EUR) | 120,000 EUR |
| Ever applied/interviewed here before? | Track per company in §7 |
| How did you hear about us? | Default: "Company careers page" (change if referred) |
| Gender / ethnicity / veteran / disability (EEO) | Your choice — "Decline to self-identify" is always acceptable |

---

## 2. The 30-second positioning statement

> Use this for "Tell us about yourself", LinkedIn summary, and the top of cover letters.

I'm an AI Product Manager with 8+ years across telecom, healthcare, insurance and banking,
including 3 years owning production AI systems end to end — multimodal computer vision,
LLM document intelligence, and agentic workflows at national scale. My work sits on the
unglamorous side of AI products: problem framing, evaluation standards, false-positive
tolerance, and human-in-the-loop escalation design. The clearest example is a vision
platform I own at PwC that validates maintenance proof-of-work across 300,000 telecom
towers — 10,000 inspections a month at 90%+ accuracy, which replaced 20% sample-based
manual QA with 100% real-time coverage and took 500+ quality engineers off 15-minute
per-site checks.


**Shorter variant (one line, for "headline" fields):**

AI PM with 8+ years shipping production AI — computer vision, LLM document intelligence and agentic workflows at national scale.


---

## 3. Proof bank — the numbers you can defend

Use these instead of adjectives. Every one is defensible in interview.

| Metric | Context | Nuance to state if pushed |
|---|---|---|
| 300,000 towers | Scale of telecom tower estate covered | 3 lakh towers in India, quarterly maintenance cycle |
| 10,000 inspections/month | Live production volume | ~100 tickets/day |
| 90%+ accuracy on 8 of 11 checkpoints | Vision model performance | Remaining 3 checkpoints at 85%+ |
| 2–3% false positive ceiling | The tradeoff *you* set | Chose accuracy over inference cost deliberately |
| 70% of QA workflow automated | Phase 1 scope | 11 of ~20 checkpoints, foundation section only |
| 2 in 10 → 10 in 10 sites validated | Coverage change | Before: sampled QA. After: 100% real-time |
| 500+ quality engineers | Users affected, across 8 circles | They now review only AI-flagged non-compliance |
| 15–20 min → near-zero per site | Cycle time | Only defected sites now reach a human |
| 1,000+ contracts/month | IDP volume | MSAs, SOWs, addenda, extension letters |
| 85% document-level accuracy | Contract extraction | Across 50+ fields; document-level, not field-level |
| 65+ page documents | Chunking challenge | Drove the RAG + chunking design |
| ~700 hours saved per user annually | IDP business value | 30–35 contracts/day × 20 min each |
| 2,000 submissions/month | Xceedance insurance RPA | UiPath Document Understanding, OCR + NLP |
| 80% AHT reduction | Xceedance | Average handling time |
| 10,000 invoices/month, 26 departments | Grid Infocom, Australian children's hospital | 85% of billing validation automated |
| Top 10% of 9,100 teams | Google Agentic AI Hackathon, July 2025 | 57,000+ developers; reached in-person final |

---

## 4. STAR stories — the interview core

### S1. Vision platform for tower maintenance QA *(flagship — lead with this)*
- **Situation:** One of India's largest telecom infra operators maintains 300,000 towers on a quarterly cycle. Partners upload proof-of-work images per checkpoint. A 500+ person quality team could only validate 2 in 10 sites, at 15–20 min each.
- **Task:** I owned the product — framing what "automated proof-of-work validation" should mean, what accuracy bar mattered, and where humans stay in the loop.
- **Action:** Scoped phase 1 to 11 foundation checkpoints (base plate presence, pedestal cracks, rust). Directed model strategy across classical CV (DETR, YOLO) and GPT-4/5-series vision models, using model chaining, distillation and fine-tuning on Azure AI Foundry. **Set the false-positive ceiling at 2–3% and explicitly chose accuracy over inference cost** — a false accept means an unsafe tower passes. Designed the escalation ladder: partner gets up to 3 re-submissions, then a human reviewer approves the ticket. Validated on a golden dataset pre-UAT, then collected per-image user feedback during UAT and closed the loop by expanding chain-of-thought prompts, curating few-shot exemplars, and retraining DETR/YOLO on on-field images.
- **Result:** 90%+ accuracy on 8 of 11 checkpoints, 85%+ on the rest. 70% of the QA workflow automated. Coverage went from 20% sampled to 100% real-time across 8 circles, ~10,000 inspections and ~100 tickets/day.
- **What I'd do differently:** Phase 1 covered 11 of ~20 checkpoints. I'd have pushed harder on instrumenting *reviewer override rates* per checkpoint from day one — it's the cleanest signal of which checkpoints are genuinely production-ready.

### S2. LLM contract & invoice extraction (IDP)
- **Situation:** 1,000+ contracts, MSAs, SOWs and addenda per month; each took ~20 minutes of manual reading and re-keying into the contract management platform.
- **Task:** Lead the extraction engine as a product, not a demo — including cost and data-residency constraints.
- **Action:** Architected with engineering: PaddleOCR + chunked RAG retrieval feeding Phi-4 extraction, with Llama fine-tuned via QLoRA. Benchmarked Llama vs Qwen 2.5. **Self-hosted inside the PwC network specifically to remove per-token cost and latency ceilings.** Designed error controls: retrieval grounding to suppress hallucination, mandatory-field validation rules that block contract creation on failure, and a business-user review gate before fields post via API as a draft contract.
- **Result:** 85% document-level accuracy across 50+ fields (prose, tabular, single-token) on 65+ page documents. 30–35 contracts/day now flow through. ~700 hours saved per user annually.
- **Honest limitation:** 85% is document-level. The residual 15% is caught by the human review gate — the product design assumes the model is a drafting tool, not the system of record.

### S3. AI patient outreach for a healthcare NGO *(shows user research + 0→1)*
- **Situation:** Anushkaa Foundation prevents lifelong disability in ~1,000 Indian children born with clubfoot each year, aligned to the government RBSK programme.
- **Task:** Define AI product strategy and MVP scope from scratch.
- **Action:** Ran a 6-week field study from 21 April 2025 across 6 government hospitals with patients, ASHA workers and clinicians. Isolated three root failures: late diagnosis (families learning of treatment 6–7 months post-birth), unstructured ASHA sensitisation, and Excel-bound reporting. Converted that into a prioritised agent roadmap: a QR-triggered CV Clubfoot Detector (3-image capture → placement/quality model → classification + Pirani score), IVR/WhatsApp reminder and relapse follow-up agents, a text-and-voice awareness chatbot on LangGraph, and regional-language translation.
- **Result:** POC scope defined and approved. **State plainly that this reached POC, not production** — the value here is the research-to-roadmap chain, and interviewers respect the honesty.

### S4. A tradeoff I owned *(for "tell me about a hard decision")*
Use the 2–3% false-positive ceiling from S1. The framing: in tower safety QA, a false negative costs a re-review; a false positive means an unsafe structure is signed off. Asymmetric cost → I set precision as the binding constraint and accepted higher inference cost, then defended that cost position to stakeholders.

### S5. Working with a very small team
Single engineer, single architect on the flagship platform. Good answer for "how do you operate with constrained resources" — it forced ruthless checkpoint prioritisation (11 of 20, foundation section first) rather than breadth.

### S6. Side project — agentic building
Building a battery recommendation system for a B2C product using Claude Code. Also: Google Agentic AI Hackathon (July 2025), "Agentic AI co-pilot for farmers, guiding decisions from crop to market" — top 10% of 9,100 teams / 57,000+ developers, reached the in-person final.

---

## 5. Common application questions — reusable answers

> **Read this first:** answers here are *raw material*, not submit-ready text. Always
> re-personalise. Several companies (Anthropic explicitly) ask you not to use AI assistance
> on personal-response questions — see §6.

### "Why do you want to work here?" — how to build it, not a canned answer
The structure that works: **(1)** a specific thing the company shipped or published that you actually have an opinion on → **(2)** the connection to a real problem you have hit in your own work → **(3)** what you'd want to own there. Fill §7 per company so this is 5 minutes, not 40.

### "What's your greatest strength as a PM?"
Owning the parts of AI products that don't demo well — evaluation standards, false-positive tolerance, escalation design. Anyone can ship a model that looks impressive in a deck; the tower platform only got to production because I set an explicit precision ceiling and designed what happens on the 3rd failed re-submission.

### "Biggest weakness / area of growth"
Consulting-shaped background: I have owned AI products end to end, but under a Senior Consultant title with client-engagement rhythms rather than a continuous product org. What I'm deliberately building is the longer feedback loop — living with a product past launch, owning retention and iteration over quarters rather than handing over at hypercare. <!-- TODO: adjust if this doesn't feel true to you -->

### "Why are you leaving / why now?"
I've taken AI from POC to production inside consulting, and the constraint I keep hitting is time horizon — engagements end. I want to own a product where I see the second and third iteration. <!-- TODO: personalise -->

### "Tell us about a product you admire"
<!-- TODO: pick 2 and write 4 lines each. Choose products you genuinely use.
     Have one AI product and one non-AI product ready. -->

### "What would you do in your first 90 days?"
Template: 30 days — learn the eval harness and where the model actually fails today; talk to whoever handles escalations. 60 days — instrument the failure modes nobody is measuring. 90 days — ship one change to the human-in-the-loop path and show the override rate move.

### "Do you have experience with [X] we didn't see on your resume?"
See §8 gap handling.

### "Anything else we should know?" / "Additional information"
```copy-paste
Two things that aren't obvious from the CV: my AI work is production, not pilot — the tower
vision platform runs ~10,000 inspections a month across 8 circles today. And I work hands-on,
not just in specs: I set model strategy across DETR/YOLO and GPT-4/5-series vision models,
made the fine-tuning and distillation calls, and built a QLoRA fine-tune for contract
extraction. I'm also building an agentic side project with Claude Code, and reached the
in-person final of Google's Agentic AI Hackathon (top 10% of 9,100 teams).
```

---

## 6. ⚠️ AI-assistance policies — do not automate these

Several companies explicitly ask applicants **not** to use AI for parts of the application.
`/prep` will flag these and will **not** draft an answer — it will surface your raw material
so you can write it yourself.

| Company | Policy | What it means |
|---|---|---|
| **Anthropic** | Application asks you to confirm you have not used AI assistance for personal-response questions (e.g. "Why Anthropic?"). | Write "Why Anthropic?" yourself, in your own voice. `/prep` gives you bullet points only. |
| Others | Read each form's preamble. | If the form says it, honour it. |

**Why this matters practically:** these answers are read by humans who read hundreds of
AI-written paragraphs a week. The generic ones are obvious and they are a fast reject.
Your specific numbers (2–3% false positive ceiling, 300,000 towers, 3 re-submissions then
human) are the thing no model can invent for you. That is your actual advantage — use it.

---

## 7. Per-company notes *(you maintain this — it's the highest-leverage section)*

> For each target, jot 3–5 lines: what they shipped that you have an opinion on, who you know
> there, whether you've applied before, and what you'd want to own. Two sentences beats blank.

### Anthropic
- Applied before: <!-- TODO: yes/no + date -->
- Contacts: <!-- TODO -->
- What I have an opinion on: <!-- TODO -->
- What I'd want to own: <!-- TODO -->

### OpenAI
- Applied before: <!-- TODO -->
- Contacts: <!-- TODO -->
- What I have an opinion on: <!-- TODO -->

### Google DeepMind
<!-- TODO -->

### Sierra
<!-- TODO -->

### Harvey
<!-- TODO -->

### Sarvam AI
<!-- TODO -->

<!-- Add sections as roles come in. /prep will tell you which company section is empty. -->

---

## 8. Known gaps & how to handle them

| Likely objection | Your response |
|---|---|
| "No pure product title" | True — the title is Senior Consultant, the work is PM. Lead with ownership: I framed the problem, set the accuracy bar, owned the escalation design and the cost tradeoff. Say it plainly rather than obscuring the title. |
| "Consulting, not product company" | Reframe as: shipped to production, live today, 500+ daily users, still running. Not a deck. |
| "No B2C / no consumer scale" | Accurate. Nearest evidence: 500+ internal users, 300k tower estate, B2C battery recommender side project. Don't overclaim. |
| "No A/B testing / growth metrics" | Honest gap. What you do have is model evaluation rigour — golden datasets, precision ceilings, UAT feedback loops. Offer that as the adjacent skill. |
| "Healthcare project was only POC" | Say so upfront. Volunteering the limitation buys credibility for the numbers you *do* claim. |
| "Needs visa sponsorship" | Can't be argued away. Counter with: open to relocation, targeting their non-US offices, available at <!-- TODO: notice period -->. |
| "8 years but 3 in AI" | Frame the first 5 as automation/RPA → the same discipline (process decomposition, exception handling, human escalation) applied pre-LLM. It's continuity, not a pivot. |

---

## 9. Resume tailoring rules for `/prep`

When tailoring against a JD:
1. **Never invent.** Only reuse facts from §3, §4 and the master CV. If the JD wants something absent, list it as a gap — do not manufacture it.
2. **Mirror their vocabulary.** If the JD says "evals", use "evals" not "model evaluation metrics". If it says "agents", lead with the agentic work.
3. **Reorder, don't rewrite.** Lead with the project closest to their domain: infra/model-layer → S1; enterprise/document/legal → S2; 0→1, research, social impact → S3.
4. **Rewrite only the summary block** (3 bullets at top) per role. Body bullets get reordered and lightly reworded, not re-authored.
5. **One page.** If something is added, something is cut.
6. **Flag every keyword in the JD that has no honest backing** so Shruti decides whether to address it in the cover letter or skip the role.

---

## 10. Master CV source files
- `Shruti-Kukreja-AI-PM-CV.pdf` — current PDF for upload
- `Shruti-Kukreja-AI-PM-Resume-Claude.docx` — editable master
- `CV-Gap-Questions.md` — the long-form source interview behind every number above
