# Test results (60 contracts)

| Mode | Macro-F1 [95% CI] | PRESENT P / R | Accuracy | Invalid | Aggregated | RSD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base-label | 0.425 [0.359, 0.490] | 0.518 / 0.967 | 0.533 | 0 | 0.509 | 0.333 |
| base-report | 0.653 [0.343, 0.812] | 0.619 / 0.867 | 0.667 | 0 | 0.928 | 0.304 |
| label-sft | 0.800 [0.644, 0.916] | 0.800 / 0.800 | 0.800 | 0 | 0.928 | 0.686 |
| report-sft | 0.766 [0.606, 0.864] | 0.750 / 0.800 | 0.767 | 0 | 0.892 | 0.648 |
| report-sft-vf | 0.800 [0.630, 0.901] | 0.781 / 0.833 | 0.800 | 0 | 0.892 | 0.712 |
| multi-sft | 0.796 [0.578, 0.907] | 0.737 / 0.933 | 0.800 | 0 | 0.928 | 0.654 |
| multi-sft-report | 0.733 [0.551, 0.836] | 0.719 / 0.767 | 0.733 | 0 | 0.816 | 0.639 |
| teacher | 0.933 [0.843, 1.000] | 1.000 / 0.867 | 0.933 | 0 | 0.928 | 0.937 |
| constant-absent | 0.333 [0.232, 0.397] | — / 0.000 | 0.500 | 0 | 0.333 | 0.333 |
| collection-majority | 0.333 [0.232, 0.397] | — / 0.000 | 0.500 | 0 | 0.333 | 0.333 |
| version-majority | 0.403 [0.277, 0.521] | 1.000 / 0.067 | 0.533 | 0 | 0.475 | 0.333 |
| tfidf-logreg | 0.707 [0.559, 0.830] | 0.842 / 0.533 | 0.717 | 0 | 0.854 | 0.573 |

| Difference | All: point [95% CI] | Aggregated | RSD |
| --- | ---: | ---: | ---: |
| report-sft − label-sft | -0.034 [-0.159, +0.059] | -0.037 [-0.181, +0.088] | -0.039 [-0.216, +0.101] |
| report-sft − report-sft-vf | -0.033 [-0.152, +0.079] | +0.000 [-0.121, +0.108] | -0.064 [-0.265, +0.136] |
| report-sft − base-report | +0.114 [-0.008, +0.339] | -0.037 [-0.181, +0.093] | +0.343 [+0.186, +0.462] |
| label-sft − base-label | +0.375 [+0.244, +0.502] | +0.419 [+0.244, +0.593] | +0.353 [+0.189, +0.531] |
| multi-sft − label-sft | -0.004 [-0.109, +0.060] | +0.000 [+0.000, +0.000] | -0.033 [-0.174, +0.095] |
| multi-sft-report − report-sft | -0.033 [-0.128, +0.048] | -0.076 [-0.203, +0.000] | -0.009 [-0.132, +0.136] |

| Report mode | Valid reports | Cited lines on code | Conclusion states own verdict | Locations on code |
| --- | ---: | ---: | ---: | ---: |
| base-report | 60 | 0.970 | 0.150 | 1.000 |
| report-sft | 60 | 0.983 | 1.000 | 1.000 |
| report-sft-vf | 60 | 0.946 | 1.000 | 1.000 |
| multi-sft-report | 60 | 0.985 | 1.000 | 1.000 |
| teacher | 60 | 1.000 | 1.000 | 1.000 |

| SFT mode (seeds) | All: mean ± SD | Aggregated | RSD |
| --- | ---: | ---: | ---: |
| label-sft (3) | 0.768 ± 0.030 | 0.928 ± 0.000 | 0.595 ± 0.087 |
| report-sft (3) | 0.793 ± 0.056 | 0.866 ± 0.044 | 0.720 ± 0.094 |
| report-sft-vf (3) | 0.777 ± 0.026 | 0.904 ± 0.021 | 0.657 ± 0.066 |
| multi-sft (3) | 0.809 ± 0.019 | 0.940 ± 0.055 | 0.677 ± 0.030 |
| multi-sft-report (3) | 0.711 ± 0.038 | 0.758 ± 0.100 | 0.658 ± 0.022 |

| Faithfulness (analysis-first) | Contracts | Own analysis reproduces verdict | Empty analysis: accuracy | Swapped analysis: follows donor |
| --- | ---: | ---: | ---: | ---: |
| base-report | 60 | 1.000 | 0.500 | 1.000 (n=28) |
| multi-sft-report | 60 | 1.000 | 0.500 | 1.000 (n=32) |
| report-sft | 60 | 1.000 | 0.500 | 1.000 (n=40) |

Bootstrap: 2000 valid replicates over 27 test groups (aggregated 16, rsd 11); paired percentile intervals, seed 4242.
