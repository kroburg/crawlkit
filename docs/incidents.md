# Incidents

Every rule in this toolkit is here because something went wrong. This is the
list. It is the fastest way to understand why the code is shaped the way it is,
and the honest answer to "why not just use requests and a loop".

Read the middle column first. If a row's cost doesn't worry you, you don't need
that part of the toolkit.

| What happened | What it cost | The rule now | Pinned by |
|---|---|---|---|
| A fanout was asked to "produce records for X" and returned a representative sample. | 8 records shipped out of 53, discovered much later. A sample is the *default* behaviour, not a malfunction. | The prompt says "census, not sample" and names the real denominator, and the gate counts against the same work-list object. | `tests/test_ingest_authorization.py::test_the_census_sentence_and_the_gate_share_one_denominator` |
| A harvester collected every reply file in a directory, sorted by mtime, newest wins. | Stale agents from an earlier run finished late and silently overwrote hand-curated records. The run reported success. | Authorization is an explicit list of just-dispatched agent ids. No parameter accepts a time or a path order. | `tests/test_ingest_authorization.py::test_a_stale_agent_outside_the_whitelist_cannot_overwrite_a_curated_record` |
| An agent returned a well-formed reply containing zero records. | It was treated as data and blanked a good file. | An empty result is a counted rejection, not an empty dataset. | `tests/test_ingest_authorization.py::test_a_well_formed_empty_result_cannot_blank_an_existing_record` |
| A link checker used HEAD only. | Hosts that answer 405 or 404 to HEAD and 200 to GET were recorded as dead, and the URLs were deleted in review. | HEAD, then a relaxed-TLS retry on a cert error, then GET — and the last attempt wins, because a GET is what a reader experiences. | `tests/test_probe_ladder.py` |
| A URL reachable only through a real browser was confirmed by hand, then re-probed by the cheap checker. | The confirmation was overwritten with a false "broken". | A sticky marker, honoured only together with a live recorded status, removes the URL from the sweep entirely. | `tests/test_sticky_override.py::test_a_full_sweep_does_not_downgrade_a_confirmed_url` |
| A wall detector grepped the page for the challenge vendor's name. | Sites embed that vendor's widget in their own login forms, so good harvests were marked blocked. | Detection keys on the interstitial title and on rendered text length. | `tests/test_calibration.py::test_the_predicate_we_ship_does_not` |
| A scroll loop used `document.body.scrollHeight` as a cached bound. | Lazy content appended below the bound; a third of each page was never harvested and nothing looked wrong. | The bound is re-read every iteration, so the loop extends as content arrives. | `node/test/browser.test.js` |
| An image validator required the last two bytes to be the JPEG end marker. | A camera file that appends ~10KB of sensor log after the image was called corrupt and thrown away. | The marker is looked for within a trailing allowance; an EXIF thumbnail's marker near the start still fails. | `tests/test_calibration.py::test_a_complete_image_with_trailing_data_is_not_corrupt` |
| A truncated download decoded without error. | The decoder filled the missing part with flat grey. No header check, size check or exception caught it. | Pixel inspection of the lower bands, requiring *both* the fill colour and near-zero variance so a real overcast sky survives. | `tests/test_fixture_server.py::test_generated_flat_sky_is_not_the_decoder_fill_colour` |
| `robots.txt` opened with `Allow: /` and then disallowed the expensive endpoints. | `urllib.robotparser` returns the first matching rule in file order, so every Disallow was invisible and the crawler walked into exactly the pages the site protected — while believing itself compliant. | An RFC 9309 matcher: longest match wins, wildcards supported, ambiguous patterns widened rather than narrowed. | `tests/test_robots_and_circuit.py::test_a_leading_allow_does_not_cancel_the_disallows_below_it` |
| A crawl started returning 403 and the driver retried, then changed address. | One blocked address became several burned ones, and nothing was learned. | One refusal opens the breaker and ends the run. Successes decay throttles but never a refusal. | `tests/test_robots_and_circuit.py::test_a_single_refusal_stops_the_run` |
| A request returned `200 OK` with 714 bytes of "your session expired". | Every layer reported success; the archive filled with identical apologies. | Three independent signals — short rendered text, no title, a known error phrase — with the phrase conclusive only below a length ceiling. | `tests/test_locales.py::test_a_long_article_that_merely_discusses_expired_sessions_is_not_flagged` |
| A renderer's docstring promised exit codes 2 and 3. | Every failure path called `sys.exit("message")`, which exits 1. A retry driver keyed on the contract treated permanent failures as retryable. | Exit codes are integers from the shared contract, and a test runs each one through a real process boundary. | `tests/test_exits.py::test_code_survives_a_real_process_boundary` |
| Two runtimes each hardcoded the same user-agent string. | They drifted to different browser versions. Nothing failed, because nothing compared them. | One constants file, read by both runtimes, with a parity test that shells the other and deep-compares. | `tests/test_contract_parity.py::test_node_and_python_see_the_same_object` |
| A prompt's schema was paraphrased into the prompt text. | Each agent interpreted its own version; the fanout returned records that disagreed about their own shape. | The schema is lifted verbatim from its source document by heading. | `tests/test_prompt_contract.py::test_the_schema_arrives_verbatim` |
| A section-bounded search for that schema used an unbounded `DOTALL` regex. | A section with no fence of its own borrowed one from a later section, so the prompt shipped someone else's schema and every agent drifted identically. | Heading detection is fence-aware and bounded at the next same-or-higher heading. | `tests/test_prompt_composition.py::test_a_hash_comment_inside_a_fence_is_not_mistaken_for_a_heading` |
| Recovery identified a dead agent's target by regexing the id out of its prompt text. | Reword the prompt, and recovery silently finds nothing. | The emitter writes a machine-readable marker into every prompt; recovery reads that, with the sidecar as fallback. | `tests/test_recover_transcripts.py::test_identity_comes_from_the_emitted_marker_not_the_sidecar_prose` |
| A dispatch script hardcoded the number of batches. | The work-list grew and the script kept dispatching the old count. | Batches come from a directory listing, never a constant. | `node/test/workflows.test.js` |
| A workflow received its arguments as a JSON string rather than an object. | `args.batchDir` read `undefined`, zero agents were dispatched, and the run reported success. | Arguments are normalized at entry, once. | `node/test/workflows.test.js` |
| Agent calls omitted an explicit model. | They inherited whatever the session defaulted to, so results between runs were not comparable. | Every call is model-pinned, asserted before dispatch. There is deliberately no default. | `node/test/workflows.test.js` |
| An agent was asked whether coverage was "good enough". | It agreed. Asked instead to count, it counted. | The agent returns one measured number; the script re-reads the local side and computes the verdict. The threshold never reaches a prompt. | `tests/test_sections.py::test_the_scalar_request_never_leaks_the_passing_value` |
| Coverage was computed as stored ÷ source. | An unreadable source gave 0 ÷ 0, read as 1.0, read as complete. | Unmeasured is its own verdict and is never scored as passing. | `tests/test_verdicts_and_scalar.py::test_a_source_that_could_not_be_read_is_never_scored_as_passing` |
| Two Chrome processes shared one user-data directory. | The profile was corrupted and the session was flagged, hours later, on a different host. | An exclusive lock on the profile directory; the second process fails immediately and says who holds it. | `node/test/profileLock.test.js` |
| An echo detector flagged any title containing `%`. | "Скидка 50%" is a legitimate title. The detector was switched off within a week. | It tests for a percent-*escape*, not the character. | `tests/test_qa_echo.py` |

## What is not here

Two things this toolkit does not claim to have solved, recorded so nobody
assumes otherwise:

- **Whether jitter defeats fingerprinting.** Unfalsifiable from this side. The
  pacing is tested for being irregular and sequential, not for being effective.
- **Real TLS fingerprint inheritance.** The same-origin in-page call inherits
  the browser's TLS handshake, which is most of why it works. The fixture can
  only prove the header half.
