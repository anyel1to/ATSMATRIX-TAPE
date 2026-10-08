CXX ?= g++
CARGO ?= cargo
PYTHON ?= python3

.PHONY: all engine signal render clean

all: render

engine:
	mkdir -p build
	$(CXX) -std=c++17 -O2 -o build/tape-engine engine/tape.cpp
	./build/tape-engine build

signal: engine
	cd signal && $(CARGO) build --release
	./signal/target/release/tape-signal build

render: signal
	$(PYTHON) viz/desk.py

clean:
	rm -rf build signal/target
