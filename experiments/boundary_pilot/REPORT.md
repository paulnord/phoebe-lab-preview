# Boundary preview retraining pilot

Generated 60 new native PHOEBE systems with 4 workers in 60.9 s (median 3.00 s/curve, p95 8.96 s/curve).
Each of contact, primary-donor semi-detached, and secondary-donor semi-detached received 12 boundary-focused training systems and 8 separately seeded edge holdouts.

The candidate is **not accepted** and the production preview models are unchanged. Current and candidate models use the same untouched original in-domain test systems; edge holdouts are new and absent from both fits except that the candidate sees a separate edge-training split.

The generated candidate specification is committed losslessly as `artifacts/candidate-models.json.gz` (gunzip to recover the JSON emitted by the pilot); native curves and split metadata are in `artifacts/boundary-pilot.npz`.

| Mode | Holdout | Model | RMS | p95 curve RMS | worst abs | p95 depth error | p95 ingress/egress RMS |
|---|---|---|---:|---:|---:|---:|---:|
| contact | common_holdout | current | 0.001077 | 0.001806 | 0.025301 | 0.007194 | 0.001724 |
| contact | common_holdout | candidate | 0.001082 | 0.001885 | 0.023040 | 0.006991 | 0.001795 |
| contact | edge_holdout | current | 0.001016 | 0.001451 | 0.009123 | 0.008336 | 0.001687 |
| contact | edge_holdout | candidate | 0.001046 | 0.001547 | 0.009631 | 0.008747 | 0.001605 |
| semi_primary | common_holdout | current | 0.001434 | 0.002866 | 0.020073 | 0.007971 | 0.001553 |
| semi_primary | common_holdout | candidate | 0.001179 | 0.002380 | 0.016353 | 0.009396 | 0.001927 |
| semi_primary | edge_holdout | current | 0.001729 | 0.002545 | 0.011847 | 0.007836 | 0.001390 |
| semi_primary | edge_holdout | candidate | 0.001537 | 0.002306 | 0.011106 | 0.007456 | 0.001425 |
| semi_secondary | common_holdout | current | 0.002036 | 0.003811 | 0.036466 | 0.014985 | 0.003022 |
| semi_secondary | common_holdout | candidate | 0.001827 | 0.003825 | 0.022856 | 0.016071 | 0.003488 |
| semi_secondary | edge_holdout | current | 0.003176 | 0.005334 | 0.036454 | 0.030237 | 0.004640 |
| semi_secondary | edge_holdout | candidate | 0.002328 | 0.003754 | 0.024510 | 0.022521 | 0.003167 |

## Paired mass-ratio responses already in the original sweep

These comparisons use the already-sampled native slider pairs near q edges; no new response sweep was generated. Donors remain separate.

| Donor | anchor q | model | difference RMS | cosine | relative norm error |
|---|---:|---|---:|---:|---:|
| primary | 0.460 | current | 0.000540 | 0.9639 | 0.1738 |
| primary | 0.460 | candidate | 0.000561 | 0.9557 | 0.1470 |
| primary | 1.220 | current | 0.000534 | 0.8481 | 0.3842 |
| primary | 1.220 | candidate | 0.001118 | 0.8318 | 1.3095 |
| primary | 0.440 | current | 0.000755 | 0.9801 | 0.0980 |
| primary | 0.440 | candidate | 0.000702 | 0.9832 | 0.0958 |
| secondary | 0.460 | current | 0.000377 | 0.9853 | 0.0588 |
| secondary | 0.460 | candidate | 0.000458 | 0.9799 | 0.0989 |
| secondary | 1.220 | current | 0.000459 | 0.9776 | 0.0091 |
| secondary | 1.220 | candidate | 0.000419 | 0.9811 | 0.0029 |
| secondary | 0.440 | current | 0.001307 | 0.9574 | 0.2746 |
| secondary | 0.440 | candidate | 0.001201 | 0.9525 | 0.1991 |

Native PHOEBE remains authoritative for fitting, statistics, and export. Candidate promotion requires reviewing these common and edge holdouts; this pilot never changes fit bounds.
