// ATSMATRIX TAPE — simulated book, trade prints, and the frame raster.
// No market data. No orders leave the machine.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr int W = 1200;
constexpr int H = 680;
constexpr int TICKS = 336;

struct Tick {
  int i = 0;
  double mid = 0;
  double bid = 0;
  double ask = 0;
  double bid_sz = 0;
  double ask_sz = 0;
  double last = 0;
  int side = 0;
  double qty = 0;
  double bid_lvl[5]{};
  double ask_lvl[5]{};
};

struct Image {
  int w = W;
  int h = H;
  std::vector<uint8_t> px;
  explicit Image(int w, int h) : w(w), h(h), px(static_cast<size_t>(w * h * 3), 0) {}
  void plot(int x, int y, uint8_t r, uint8_t g, uint8_t b) {
    if (x < 0 || y < 0 || x >= w || y >= h) return;
    size_t i = static_cast<size_t>((y * w + x) * 3);
    px[i] = r;
    px[i + 1] = g;
    px[i + 2] = b;
  }
  void blend(int x, int y, uint8_t r, uint8_t g, uint8_t b, float a) {
    if (x < 0 || y < 0 || x >= w || y >= h || a <= 0) return;
    if (a > 1) a = 1;
    size_t i = static_cast<size_t>((y * w + x) * 3);
    px[i] = static_cast<uint8_t>(px[i] * (1 - a) + r * a);
    px[i + 1] = static_cast<uint8_t>(px[i + 1] * (1 - a) + g * a);
    px[i + 2] = static_cast<uint8_t>(px[i + 2] * (1 - a) + b * a);
  }
  void fill(int x, int y, int rw, int rh, uint8_t r, uint8_t g, uint8_t b) {
    for (int yy = y; yy < y + rh; ++yy)
      for (int xx = x; xx < x + rw; ++xx) plot(xx, yy, r, g, b);
  }
  void disc(int cx, int cy, int rad, uint8_t r, uint8_t g, uint8_t b, float a) {
    for (int y = -rad; y <= rad; ++y)
      for (int x = -rad; x <= rad; ++x)
        if (x * x + y * y <= rad * rad) blend(cx + x, cy + y, r, g, b, a);
  }
};

uint32_t rng = 0xA75E17u;
uint32_t nextr() {
  rng ^= rng << 13;
  rng ^= rng >> 17;
  rng ^= rng << 5;
  return rng;
}
double uni() { return (nextr() & 0xFFFFFFu) / double(0x1000000u); }
double gauss() {
  double u = std::max(1e-6, uni());
  double v = std::max(1e-6, uni());
  return std::sqrt(-2 * std::log(u)) * std::cos(6.28318530718 * v);
}

std::vector<Tick> simulate() {
  std::vector<Tick> out;
  out.reserve(TICKS);
  double mid = 100.0;
  int regime = 0;
  int left = 28;
  for (int i = 0; i < TICKS; ++i) {
    if (--left <= 0) {
      regime = static_cast<int>(nextr() % 3);
      left = 36 + static_cast<int>(nextr() % 28);
    }
    double drift = regime == 0 ? 0.035 : regime == 1 ? -0.032 : -0.08 * (mid - 100.0);
    mid += drift + gauss() * 0.085;
    mid = std::clamp(mid, 94.0, 106.0);
    double spread = 0.02 + uni() * 0.03;
    double imb = std::tanh(gauss() * 0.7 + (regime == 0 ? 0.25 : regime == 1 ? -0.25 : 0));
    double base = 80 + uni() * 140;
    Tick t;
    t.i = i;
    t.mid = mid;
    t.bid = mid - spread * 0.5;
    t.ask = mid + spread * 0.5;
    t.bid_sz = base * (1.0 + imb);
    t.ask_sz = base * (1.0 - imb);
    t.side = 0;
    t.qty = 0;
    t.last = mid;
    if (uni() < 0.72) {
      t.side = uni() < 0.5 + imb * 0.25 ? 1 : -1;
      t.qty = 1 + uni() * 18;
      t.last = t.side > 0 ? t.ask : t.bid;
      if (t.side > 0) t.ask_sz = std::max(8.0, t.ask_sz - t.qty);
      else t.bid_sz = std::max(8.0, t.bid_sz - t.qty);
    }
    for (int k = 0; k < 5; ++k) {
      double decay = std::exp(-0.35 * k);
      t.bid_lvl[k] = t.bid_sz * decay * (0.75 + uni() * 0.5);
      t.ask_lvl[k] = t.ask_sz * decay * (0.75 + uni() * 0.5);
    }
    out.push_back(t);
  }
  return out;
}

void write_csv(const std::vector<Tick>& tape, const std::string& path) {
  std::ofstream f(path);
  f << "i,mid,bid,ask,bid_sz,ask_sz,last,side,qty";
  for (int k = 0; k < 5; ++k) f << ",b" << k << ",a" << k;
  f << "\n";
  f.setf(std::ios::fixed);
  f.precision(5);
  for (const Tick& t : tape) {
    f << t.i << "," << t.mid << "," << t.bid << "," << t.ask << "," << t.bid_sz << "," << t.ask_sz << ","
      << t.last << "," << t.side << "," << t.qty;
    for (int k = 0; k < 5; ++k) f << "," << t.bid_lvl[k] << "," << t.ask_lvl[k];
    f << "\n";
  }
}

void render(const std::vector<Tick>& tape, int upto, const std::string& path) {
  Image im(W, H);
  im.fill(0, 0, W, H, 12, 16, 22);
  for (int y = 72; y < 500; y += 36) {
    for (int x = 78; x < 910; ++x) im.blend(x, y, 80, 96, 120, 0.12f);
  }
  double lo = 1e9, hi = -1e9;
  for (int i = 0; i <= upto; ++i) {
    lo = std::min(lo, tape[static_cast<size_t>(i)].mid);
    hi = std::max(hi, tape[static_cast<size_t>(i)].mid);
  }
  double pad = std::max(0.15, (hi - lo) * 0.18);
  lo -= pad;
  hi += pad;
  auto py = [&](double price) {
    double u = (price - lo) / (hi - lo);
    return 500 - static_cast<int>(u * 400);
  };
  auto px = [&](int i) {
    return 78 + static_cast<int>((i / static_cast<double>(TICKS - 1)) * 820);
  };

  const int group = 4;
  for (int g = 0; g * group <= upto; ++g) {
    int a = g * group;
    int b = std::min(upto, a + group - 1);
    double o = tape[static_cast<size_t>(a)].mid;
    double c = tape[static_cast<size_t>(b)].mid;
    double h = o, l = o;
    double vol = 0;
    for (int i = a; i <= b; ++i) {
      h = std::max(h, tape[static_cast<size_t>(i)].mid);
      l = std::min(l, tape[static_cast<size_t>(i)].mid);
      vol += tape[static_cast<size_t>(i)].qty;
    }
    int x = px(a);
    bool up = c >= o;
    uint8_t r = up ? 72 : 232;
    uint8_t gg = up ? 196 : 96;
    uint8_t bb = up ? 150 : 112;
    int y1 = py(h), y2 = py(l);
    for (int y = std::min(y1, y2); y <= std::max(y1, y2); ++y) im.plot(x + 3, y, r, gg, bb);
    int top = py(std::max(o, c));
    int bot = py(std::min(o, c));
    if (bot - top < 3) bot = top + 3;
    im.fill(x, top, 6, bot - top, r, gg, bb);
    int vh = static_cast<int>(std::min(40.0, vol * 0.4));
    im.fill(x, 548 - vh, 6, vh, r, gg, bb);
  }

  for (int i = 0; i <= upto; ++i) {
    const Tick& t = tape[static_cast<size_t>(i)];
    if (t.side == 0) continue;
    float age = 1.f - float(upto - i) / 36.f;
    if (age <= 0) continue;
    int rad = 2 + static_cast<int>(std::min(5.0, t.qty / 6));
    if (t.side > 0) im.disc(px(i), py(t.last), rad, 110, 220, 180, 0.22f * age);
    else im.disc(px(i), py(t.last), rad, 230, 120, 130, 0.22f * age);
  }

  const Tick& now = tape[static_cast<size_t>(upto)];
  int ly = py(now.last);
  for (int x = 78; x < 910; ++x) im.blend(x, ly, 232, 236, 242, 0.45f);
  im.disc(px(upto), ly, 4, 232, 236, 242, 1.f);
  for (int y = 56; y < 560; ++y) im.blend(928, y, 80, 96, 120, 0.35f);

  double maxsz = 1;
  for (int k = 0; k < 5; ++k) {
    maxsz = std::max(maxsz, now.bid_lvl[k]);
    maxsz = std::max(maxsz, now.ask_lvl[k]);
  }
  for (int k = 0; k < 5; ++k) {
    int bw = static_cast<int>(150 * now.bid_lvl[k] / maxsz);
    int aw = static_cast<int>(150 * now.ask_lvl[k] / maxsz);
    im.fill(980, 168 + k * 22, bw, 14, 78, 150, 230);
    im.fill(980, 70 + (4 - k) * 22, aw, 14, 214, 112, 122);
  }

  int row = 0;
  for (int i = upto; i >= 0 && row < 8; --i) {
    const Tick& t = tape[static_cast<size_t>(i)];
    if (t.side == 0) continue;
    int y = 360 + row * 22;
    uint8_t r = t.side > 0 ? 61 : 255;
    uint8_t g = t.side > 0 ? 196 : 107;
    uint8_t b = t.side > 0 ? 154 : 128;
    int w = 16 + static_cast<int>(std::min(110.0, t.qty * 5));
    im.fill(980, y, w, 12, r, g, b);
    ++row;
  }

  im.fill(0, 590, W, 90, 10, 13, 18);

  std::ofstream f(path, std::ios::binary);
  f << "P6\n" << W << " " << H << "\n255\n";
  f.write(reinterpret_cast<const char*>(im.px.data()), static_cast<std::streamsize>(im.px.size()));
}

}  // namespace

int main(int argc, char** argv) {
  std::string dir = argc > 1 ? argv[1] : "build";
  auto tape = simulate();
  write_csv(tape, dir + "/tape.csv");
  for (int i = 8; i < TICKS; i += 2) {
    std::ostringstream name;
    name << dir << "/frame_" << i << ".ppm";
    render(tape, i, name.str());
  }
  render(tape, TICKS - 1, dir + "/frame_last.ppm");
  std::cout << "ticks " << tape.size() << "\n";
  return 0;
}
