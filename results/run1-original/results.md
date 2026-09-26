# Test results (60 contracts)

| Mode | Macro-F1 [95% CI] | PRESENT P / R | Accuracy | Invalid | Aggregated | RSD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base-label | 0.425 [0.359, 0.490] | 0.518 / 0.967 | 0.533 | 0 | 0.509 | 0.333 |
| base-report | 0.653 [0.343, 0.812] | 0.619 / 0.867 | 0.667 | 0 | 0.928 | 0.304 |
| label-sft | 0.798 [0.673, 0.892] | 0.875 / 0.700 | 0.800 | 0 | 0.892 | 0.716 |
| report-sft | 0.697 [0.445, 0.827] | 0.667 / 0.800 | 0.700 | 0 | 0.892 | 0.491 |
| report-sft-vf | 0.790 [0.651, 0.882] | 0.793 / 0.767 | 0.783 | 1 | 0.868 | 0.716 |
| teacher | 0.933 [0.843, 1.000] | 1.000 / 0.867 | 0.933 | 0 | 0.928 | 0.937 |
| constant-absent | 0.333 [0.232, 0.397] | — / 0.000 | 0.500 | 0 | 0.333 | 0.333 |
| collection-majority | 0.333 [0.232, 0.397] | — / 0.000 | 0.500 | 0 | 0.333 | 0.333 |
| version-majority | 0.403 [0.277, 0.521] | 1.000 / 0.067 | 0.533 | 0 | 0.475 | 0.333 |
| tfidf-logreg | 0.707 [0.559, 0.830] | 0.842 / 0.533 | 0.717 | 0 | 0.854 | 0.573 |

| Difference | Point | 95% CI |
| --- | ---: | ---: |
| report-sft − label-sft | -0.101 | [-0.296, +0.036] |
| report-sft − report-sft-vf | -0.093 | [-0.265, +0.022] |
| report-sft − base-report | +0.044 | [-0.091, +0.248] |
| label-sft − base-label | +0.373 | [+0.258, +0.483] |

| Report mode | Valid reports | Cited lines on code | Conclusion states own verdict | Locations on code |
| --- | ---: | ---: | ---: | ---: |
| base-report | 60 | 0.970 | 0.150 | 1.000 |
| report-sft | 60 | 0.958 | 1.000 | 1.000 |
| report-sft-vf | 59 | 0.984 | 0.983 | 1.000 |
| teacher | 60 | 1.000 | 1.000 | 1.000 |

Bootstrap: 2000 valid replicates over 27 groups.
