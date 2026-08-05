# Tetris

Stack falling tetrominoes and clear lines.

A playable Assistant Matrix game app. Control layout: `tetris`.

Actions: `left`, `right`, `softDrop`, `hardDrop`, `rotateCw`, `rotateCcw`, `hold`, `pause`, `resume`, `togglePause`, `restart`

Install it from the Store, or package it yourself with:

```bash
poetry run assistant-matrix-app validate app.toml
poetry run assistant-matrix-app package . --output-dir dist
```
