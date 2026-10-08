// Online desk signal. Weights are written down in the README.
// This is not a forecast and it is not trained on a market.

use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader, Write};

struct Row {
    i: i32,
    mid: f64,
    bid_sz: f64,
    ask_sz: f64,
}

fn main() {
    let dir = env::args().nth(1).unwrap_or_else(|| "build".into());
    let inp = File::open(format!("{dir}/tape.csv")).expect("tape.csv");
    let mut rows = Vec::new();
    for (n, line) in BufReader::new(inp).lines().enumerate() {
        let line = line.expect("read");
        if n == 0 {
            continue;
        }
        let c: Vec<&str> = line.split(',').collect();
        if c.len() < 6 {
            continue;
        }
        rows.push(Row {
            i: c[0].parse().unwrap_or(0),
            mid: c[1].parse().unwrap_or(0.0),
            bid_sz: c[4].parse().unwrap_or(0.0),
            ask_sz: c[5].parse().unwrap_or(0.0),
        });
    }

    let mut out = File::create(format!("{dir}/signals.csv")).expect("signals.csv");
    writeln!(
        out,
        "i,imbalance,mom,vol,score,confidence,bias,regime,position,pnl"
    )
    .unwrap();

    let mut pnl = 0.0;
    let mut prev_pos = 0.0;
    let mut prev_mid = rows.first().map(|r| r.mid).unwrap_or(1.0);

    for (idx, row) in rows.iter().enumerate() {
        let past = |k: usize| -> f64 {
            if idx >= k {
                rows[idx - k].mid
            } else {
                row.mid
            }
        };
        let imb_den = (row.bid_sz + row.ask_sz).max(1.0);
        let imb = (row.bid_sz - row.ask_sz) / imb_den;
        let ret8 = (row.mid - past(8)) / past(8).max(1.0);
        let ret24 = (row.mid - past(24)) / past(24).max(1.0);
        let mut vol = 0.0;
        let window = idx.min(12);
        if window > 0 {
            for k in 1..=window {
                vol += ((rows[idx - k + 1].mid - rows[idx - k].mid) / rows[idx - k].mid).abs();
            }
            vol /= window as f64;
        }
        let score = (1.6 * imb + 90.0 * ret8 + 46.0 * ret24).clamp(-3.0, 3.0);
        let confidence = score.abs().tanh();
        let bias = if score > 0.05 {
            1
        } else if score < -0.05 {
            -1
        } else {
            0
        };
        let regime = if vol < 0.00055 && ret24.abs() < 0.0012 {
            "chop"
        } else if ret8 * ret24 > 0.0 && ret24.abs() > 0.0016 {
            "trend"
        } else {
            "revert"
        };
        let position = if confidence > 0.42 { bias as f64 } else { 0.0 };
        let ret = (row.mid - prev_mid) / prev_mid.max(1.0);
        pnl += prev_pos * ret;
        prev_pos = position;
        prev_mid = row.mid;
        writeln!(
            out,
            "{},{:.5},{:.6},{:.6},{:.5},{:.5},{},{},{:.0},{:.6}",
            row.i, imb, ret8, vol, score, confidence, bias, regime, position, pnl
        )
        .unwrap();
    }
}
