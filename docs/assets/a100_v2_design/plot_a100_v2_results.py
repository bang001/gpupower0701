#!/usr/bin/env python3
"""Generate standard visualizations from A100 FP16 energy v2 result CSV."""
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = 'NanumGothic'
matplotlib.rcParams['axes.unicode_minus'] = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    ap.add_argument('--outdir', default='plots')
    args = ap.parse_args()
    out = Path(args.outdir)
    out.mkdir(exist_ok=True)
    df = pd.read_csv(args.csv)

    # pJ/FLOP vs W_SM
    if {'W_SM_KiB','pJ_per_FLOP','blocks_per_SM','mode'}.issubset(df.columns):
        for mode, g in df.groupby('mode'):
            plt.figure(figsize=(8,5))
            for b, h in g.groupby('blocks_per_SM'):
                h = h.sort_values('W_SM_KiB')
                plt.plot(h['W_SM_KiB'], h['pJ_per_FLOP'], marker='o', label=f'B={b}')
            plt.xscale('log', base=2)
            plt.xlabel('W_SM (KiB)')
            plt.ylabel('pJ/FLOP')
            plt.title(f'pJ/FLOP vs W_SM - {mode}')
            plt.legend()
            plt.grid(True, which='both', alpha=0.35)
            plt.tight_layout()
            plt.savefig(out / f'pj_flop_vs_wsm_{mode}.png', dpi=180)
            plt.close()

    # Energy vs blocks/SM
    if {'blocks_per_SM','net_E_J','W_SM_KiB','mode'}.issubset(df.columns):
        plt.figure(figsize=(8,5))
        for (mode,w), g in df.groupby(['mode','W_SM_KiB']):
            g = g.sort_values('blocks_per_SM')
            plt.plot(g['blocks_per_SM'], g['net_E_J'], marker='o', label=f'{mode}, W={w}KiB')
        plt.xscale('log', base=2)
        plt.xlabel('blocks/SM')
        plt.ylabel('Net energy (J)')
        plt.title('Energy vs blocks/SM')
        plt.legend(fontsize=7)
        plt.grid(True, which='both', alpha=0.35)
        plt.tight_layout()
        plt.savefig(out / 'energy_vs_blocks_per_sm.png', dpi=180)
        plt.close()

if __name__ == '__main__':
    main()
