# Harbor acceptance

Accepted on 2026-08-14 with Harbor 0.20.0.

## Oracle

- job: `algobridge-0010-bwa-freebayes-oracle-20260814`;
- job result ID: `a7125665-7d56-4cd0-8bb5-a97442bb55a4`;
- trials: 1 completed, 0 errored;
- Reward: `1.0`;
- hidden real differential cases: `15/15`;
- public examples: `5/5`;
- source policy, reference determinism, candidate isolation, candidate build,
  legacy BWA-MEM regression and real reference-pipeline gates: all pass.

## NOP negative control

- job: `algobridge-0010-bwa-freebayes-nop-20260814`;
- job result ID: `b6b2c797-d6bf-4844-9d01-83f95d292b21`;
- trials: 1 completed, 0 errored;
- Reward: `0.0`;
- failure point: required integration/source-policy hard gate.

The reference phase executes locked pristine BWA-MEM, samtools and real
FreeBayes before candidate execution. The candidate phase physically lacks
those executables, their sources, FreeBayes-specific dynamic libraries and
network access; it rebuilds and runs the submitted BWA as UID 10001 with
`/tests` unreadable.
