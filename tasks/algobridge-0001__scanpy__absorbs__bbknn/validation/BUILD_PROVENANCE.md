# Build provenance

Locked source commits and trees are recorded in `source-lock.json`:

- Scanpy `fabadb9412c0d1cd9df9d9c2e95ac266d564ee18`, tree
  `c68e70c22539158ed52fd8169761d818ac8510a2`;
- BBKNN `95ce34b8905cbde307704a77436c354938ba0367`, tree
  `b8705a65eefecacd34791d719de8406cb6451c8f`.

The Scanpy wheel SHA-256 is
`ec8840ca54acbbee66ecce6c4f2eb979f636c27d792c3f287404153878be7131`.
The two offline wheel manifests have SHA-256
`1acf8933308ecd19873eecf25e9d1cf08e0564cb948b9385612813dbc08e011c`.
The locked donor `bbknn/matrix.py` runtime SHA-256 is
`eebcc5ec28f172db5ca84f1888a8ffe9da0eaf97a57077e6aa0ed229b21fb19f`.

Final local Podman images used for direct acceptance:

- Agent: `ca27202f90253aecb097791ed35ea7a3c1aedc9b80336e5d26b389948e379365`;
- verifier: `3d409c3837e0fd0235b7aec11f57cb7507fafe1bc13ed7c9c442a3375e2a5730`.

Both Dockerfiles install repository-carried wheels with `--no-index`. Harbor 0.20 also rebuilt the
task with no-network Agent/verifier execution and `environment_mode = "separate"`.
