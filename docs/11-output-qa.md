# 11 — The scrape succeeded. Is the data any good?

**Every failure in this chapter looks like success at fetch time.** The request
returned 200, the parser did not raise, the file has content in it. Nothing
upstream will tell you.

## A 200 with an error in the body

An ASP-style site asked for a record without a server-side session returns
`200 OK`, 714 bytes, no title, and a polite message saying the session expired.
The probe records 200, the driver marks the item done, the sentinel is written,
and the archive fills with identical apologies nobody reads until a parser
yields nothing months later.

Three independent signals — very little rendered text, no `<title>`, a known
error phrase in an enabled locale — because each alone has honest
counter-examples. The phrase is conclusive only *below a length ceiling*: a long
article discussing expired sessions contains the same words as a short page that
is one.

## The extractor handing back its own input

A human-facing field containing a URL or a percent-escape was not read off the
page; it is the input echoed back.

Test for a percent-**escape**, not for `%`. "Скидка 50%" and "Inflation rose 5%"
are legitimate titles, and a bare check on the character condemns them — which
is how a detector gets switched off within a week.

## A parse that filled nothing

Pages saved mid-hydration parse cleanly and produce records — just thinner ones.
Nothing raises. What surfaces it is a field census: fill rate per field, sorted
ascending, so an empty-but-well-formed harvest is visible at a glance.

Comparing two censuses turns the report into a gate. Re-run the parser over the
same pages and any field whose fill rate dropped fails — which is what catches a
parser change that quietly stops finding something.

## An image that decodes and is still wrong

A JPEG cut mid-scan still opens, reports correct dimensions, and renders. The
decoder fills the missing part with flat mid-grey. No header check, size check
or exception catches it; only the pixels do.

Sample a few strips across the lower half — truncation eats the bottom of a
top-down encode — and flag a strip whose mean sits on the fill value **and**
whose variance is near zero. Both halves are load-bearing: uniformity alone
condemns every photograph of an overcast sky.

The byte-level check is the cheap first pass, and it needs one relaxation: the
end-of-image marker is looked for near the end rather than exactly at it,
because a camera file can append kilobytes of sensor log after the image
stream, and a strict check throws away a perfectly good photograph.

## A best match is not a match

Two problems, one function: which place does this record refer to, and which
target does this unlabelled verdict belong to. Both were once "take the
nearest", and both produced confident wrong answers.

`best_under` picks the closest candidate and then refuses it if it is not close
enough. Below the floor it returns nothing and the caller counts that. The
provenance carries the runner-up and the margin, so a human can see that a match
won by two metres out of fifteen hundred.

## When one pass is not enough

Only values that two independent passes both produced *and* agree on are
auto-applicable. Absence is not assent: a value present in one pass only is
disputed, never agreed.

Pinned by: `tests/test_qa_soft_error.py`, `tests/test_qa_echo.py`,
`tests/test_qa_census.py`, `tests/test_qa_agreement.py`,
`tests/test_match_floor.py`, `tests/test_calibration.py`
