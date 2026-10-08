CXX ?= g++
CARGO ?= cargo
PYTHON ?= python3

.PHONY: all engine signal render video clean

all: video

engine:
	mkdir -p build
	$(CXX) -std=c++17 -O2 -o build/tape-engine engine/tape.cpp
	./build/tape-engine build

signal: engine
	cd signal && $(CARGO) build --release
	./signal/target/release/tape-signal build

render: signal
	$(PYTHON) viz/desk.py

video: render
	ffmpeg -y -framerate 24 -i build/seq/%04d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart -crf 18 docs/tape.mp4
	@rm -f build/frame_*.ppm

clean:
	rm -rf build signal/target
