# IDAGui Plugin

You mustn't ever never ever ever use **[ImGui](https://github.com/ocornut/imgui)** to write **IDA Pro** plugins UIs.

Never!

Don't even think about it, young person.

Stop reading!

## Screenshot

[HERE](https://x.com/pmontesel/status/1958339218838818924)

## Usage

But, if you wish to... (:

```bash
./run-with-env.sh /path/to/ida -A /path/to/idb.i64
```

## Installation

- Buy [IDA Pro](https://www.hex-rays.com/) **(very important)**
- Install IDA Pro (also very important)
- `ln -s $PWD $HOME/.idapro/plugins/idagui`
- Make sure IDA is using the same python 3.12 as [uv](https://docs.astral.sh/uv/) is using
    - This step might be unnecessary for 9.2, I've heard
- `uv sync`
- See the above `Usage` section

## Development

`uv sync --all-groups && code .`

## Why?

Why not?
