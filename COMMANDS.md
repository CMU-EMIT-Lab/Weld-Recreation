# Weld Recreation Commands

This file collects the most useful commands for working with the `Weld-Recreation` codegen pipeline.

## Generate a URScript file from G-code

Use this command to convert a G-code input into a `.script` output file:

```bash
python codegen/main.py --input codegen/test_run.gcode --output codegen/test_run.script
```

## Common variants

### Dry run (generate script and print to stdout)

```bash
python codegen/main.py --input codegen/test_run.gcode --dry-run
```

### Use the socket backend to stream directly to a UR robot

```bash
python codegen/main.py --input codegen/test_run.gcode --backend socket --robot-ip 192.168.1.1
```

### Override the URScript program name

```bash
python codegen/main.py --input codegen/test_run.gcode --output codegen/test_run.script --name run_1
```

### Show parsed waypoint summary before generating

```bash
python codegen/main.py --input codegen/test_run.gcode --output codegen/test_run.script --verbose
```

## Notes

- `--output` is required when using `--backend file` unless you also use `--dry-run`.
- `--robot-ip` defaults to the value defined in `codegen/urscript_gen.py` if not provided.
- The command above assumes you are running from the repository root.
