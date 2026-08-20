# v5 Architect Log — 影響度ランキングの統計的信頼性向上（設計フェーズ）

作成者: Architect（私）
日時: 2026-08-20T13:05:47+09:00

## 0. 要約

私は、v5 Bid Manager の AC群A（影響度ランキングの統計的信頼性向上）について、`index.html` の該当コードを読解した上で、
実際に Python で3種類の数値実験（Wald近似とWilson score intervalの被覆確率比較、共通乱数法(CRN)下での
McNemar検定と独立2標本z検定の比較、実際の `outsourcing_sim` を用いた実データ検証）を行い、統計仕様を確定した。

結論:
- 各点の信頼区間には **Wilson score interval** を採用する（Waldは n=80 でも p が極端な領域で著しく不正確）。
- 低vs基準・高vs基準の「差分の有意性判定」には、**対応のある比率差の検定（McNemar検定、継続性補正あり）**を採用する。
  独立2標本z検定は不採用とする。理由は、同一base_seedによる共通乱数法(CRN)のもとでは2群が独立でないため
  理論的に不適切であることに加え、実データ検証でも相関構造が単純に「常に強い正の相関」ではないことを確認したため、
  **相関の符号・強さを仮定せずに済む頑健な手法**としてMcNemarを選ぶのが実務上最も妥当と判断した。
- 判定結果は3段階ラベル（有意 / 不確実 / 不明瞭）で表現し、既存の `direction`（単調性判定）と組み合わせる。
- 表の主ソート順（`maxAbsDeltaPt`降順）は変更しないが、段階②に渡す候補選定（`renderReverseParamChoices`の
  チェックボックスの初期選択）だけは確信度を優先するロジックへ変更する（ノイズの大きいパラメータを
  安易に段階②へ持ち込まないため）。
- 追加のAPI呼び出し・n_trials上限の変更は一切不要。既存の3回のレスポンス（`per_trial`、各trialの`seed`と
  `final_quadrant`）だけから全て計算可能であり、**実装はJS（`index.html`）のみで完結する**。`app.py`・
  `test_api.py` の変更は不要。

---

## 1. コード読解（現状把握）

### 1.1 対象コードの確認箇所

私は `product/abm-dashboard/static/index.html` の以下の関数・定数を実際に読んだ。

- `REVERSE_STAGE1_PARAMS`（464行目）: `["alpha", "k1", "budget_c0", "budget_c1", "gamma", "difficulty_0", "funds_0"]` の7個で固定。
- `REVERSE_FACTORS`（465行目）: `[0.75, 1.0, 1.25]` の3点。
- `REVERSE_STAGE1_CALLS`（475行目）: `21`（7×3）で固定。
- `dominantLeaderPct(response, strategy)`（1107行目）: `response.per_trial` を `strategy` でフィルタし、
  `final_quadrant === "dominant_leader"` のヒット数 / 全件数 × 100 を返す。**生のヒット配列は保持しておらず、
  比率だけを返している**。
- `extractStrategyMetrics(response, strategy)`（1114行目）: `dominant_leader_pct` を含む集計値オブジェクトを返す。
- `summarizeQuadrantSweep(low, base, high)`（780行目）: `deltaLowPt`, `deltaHighPt`, `maxAbsDeltaPt`, 単調性
  のみに基づく `direction`（3値: 増加方向 / 減少方向 / 「方向が一定しない」）を返す。**標準誤差・信頼区間・
  有意性判定は一切ない**。
- `runReverseStage1()`（1333行目）: `sweepNTrials = Math.min(80, Math.max(1, basePayload.n_trials))`
  （1348行目）で試行回数上限80を固定。パラメータごとに `REVERSE_FACTORS` の3点をループしてAPIを1回ずつ呼び、
  `dominantPoints`（比率のみの配列）を集めて `summarizeQuadrantSweep()` に渡している。その後
  `rows.sort((a, b) => b.maxAbsDeltaPt - a.maxAbsDeltaPt)`（1388行目）で降順ソート。
- `renderReverseStage1Table(rows)`（1130行目）: 低/基準/高の%、`direction`、`maxAbsDeltaPt`、参考の平均純利益
  を表示するテーブルを描画。末尾に「粗いランキング」「暫定値」の注意書きあり。
- `renderReverseParamChoices(rows)`（1176行目）: `rows.slice(0, 4)` を段階②のチェックボックス候補、
  `rows.slice(0, 2)` を初期チェック済み候補として使う。**つまり `maxAbsDeltaPt` の生の大小だけで段階②への
  持ち込み候補が決まる**。

### 1.2 バックエンド確認（`app.py` / `outsourcing_sim/simulate.py`）

- `app.py` の `TrialResult` モデル（66-75行目）は `seed: int`, `final_quadrant: str` を含む。
- `simulate()`（178行目）は `compare_strategies=False` の場合、`strategies = [request.params.strategy]` の
  1戦略のみを回し、`per_trial = strategy_results`（そのまま）となる。
- `outsourcing_sim/simulate.py: run_many()`（130行目）は `for i in range(n_seeds): seed = base_seed + i` と
  完全に決定的にループし、**必ず `n_seeds` 件のsummaryを、途中で欠落させることなく順番通りに返す**
  （早期終了によって件数が減ることはない）。

**確認結果**: 段階①の低/基準/高の3回の呼び出しは同じ `base_seed` を使っているため、各呼び出しの
`per_trial[i]` は必ず同じ `seed = base_seed + i` に対応する。したがって低・基準・高の3つのレスポンスから、
**`seed` フィールドをキーにして「同じ乱数種を使ったペア」を突き合わせる（ペアリングする）ことが可能**であり、
これは既存のAPIレスポンスに含まれる情報だけで完結する。バックエンドの変更は不要と判断した。

---

## 2. 数値実験1: Wald近似 vs Wilson score interval の被覆確率比較

n=80（段階①の1点あたり上限試行数）で、Wald区間とWilson区間のどちらが実用に耐えるかを、モンテカルロで検証した。

```python
def wald_ci(p_hat, n, z=1.96):
    se = np.sqrt(p_hat * (1 - p_hat) / n)
    return p_hat - z * se, p_hat + z * se

def wilson_ci(p_hat, n, z=1.96):
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    half = (z / denom) * np.sqrt((p_hat * (1 - p_hat) / n) + (z**2 / (4 * n**2)))
    return center - half, center + half
```

各真のp（0.02〜0.98）について20万回サンプリングし、95%区間が真のpを実際にカバーする割合（被覆率、目標95%）と、
Waldの下限・上限が `[0, 1]` の範囲を逸脱する（＝物理的にありえない負の割合や100%超になる）割合を測定した。

実測結果（n=80、抜粋）:

| 真のp | Wald被覆率 | Wilson被覆率 | Wald区間が[0,1]を逸脱する割合 |
|---|---|---|---|
| 0.02 | 79.95% | 97.79% | 72.32% |
| 0.05 | 90.69% | 93.63% | 41.32% |
| 0.10 | 89.91% | 96.19% | 3.53% |
| 0.20 | 93.15% | 96.53% | 0.01% |
| 0.30〜0.70 | 94.4〜94.9% | 96.3〜96.5% | 0.00% |
| 0.90 | 90.03% | 96.26% | 3.45% |
| 0.95 | 90.81% | 93.74% | 41.19% |
| 0.98 | 80.05% | 97.77% | 72.45% |

**解釈**: n=20（段階②相当）ではさらに顕著だが、n=80でも `dominant_leader_pct` が0%や100%に近い領域
（実際に段階①の実データ検証でも 100% 近傍・一桁%台の値が頻発することを§4で確認した）では、Wald近似の
被覆率が目標95%から大きく外れ（p=0.02, 0.98で約80%まで低下）、かつ7割超のケースで信頼区間の下限がマイナス
または上限が100%超という非現実的な値になる。Wilson score intervalはこれらの領域でも被覆率が目標に近く、
`[0,1]` を逸脱しない。したがって**個々の点のCI表示にはWilson score intervalを採用する**。

---

## 3. 数値実験2: 共通乱数法(CRN)下での McNemar検定 vs 独立2標本z検定

段階①は低・基準・高の3点を**同一base_seed**で実行している。これは「同じ乱数の種を共有する対応のある
（ペアの）標本」であり、Bid Managerの懸念（AC-A2.4, リスク4.1）どおり、独立2標本を仮定した
`SE_diff = sqrt(p1(1-p1)/n1 + p2(1-p2)/n2)` は理論的に不適切な可能性がある。これを疑似データで検証した。

### 3.1 モデル化

各トライアルiについて、確率rhoで「低・基準の乱数が最後まで共有された（＝CRNが効いた）ペア」とみなし
同一一様乱数から2値を生成、確率(1-rho)で「試行の途中で片方が先に終了しCRNの効果が失われた」ペアとみなし、
独立に2値を生成する、という混合モデルで擬似データを作った（rho=0で完全独立、rho=1で常に同一乱数）。

```python
def mcnemar_z(X, Y, cc=True):
    b = ((X == 1) & (Y == 0)).sum(axis=1)  # 低=hit, 基準=miss
    c = ((X == 0) & (Y == 1)).sum(axis=1)  # 低=miss, 基準=hit
    num = np.abs(b - c) - 1 if cc else (b - c)  # 継続性補正
    return num / np.sqrt(b + c)
```

n=80、10万回反復での実測結果:

**帰無仮説（真の差なし、p1=p2=0.30）下でのType I error率（目標5%）**

| rho（CRN相関の強さ） | 独立z検定 | McNemar検定 |
|---|---|---|
| 0.0（完全独立） | 5.11% | 3.13% |
| 0.3 | 1.99% | 2.75% |
| 0.6 | 0.25% | 2.32% |
| 0.9 | 0.00% | 0.32% |
| 1.0（常に同一乱数） | 0.00% | 0.00% |

**対立仮説（真の差10pt、p1=0.30→p2=0.40）下での検出力**

| rho | 独立z検定 | McNemar検定 |
|---|---|---|
| 0.0 | 27.47% | 20.62% |
| 0.3 | 24.56% | 25.50% |
| 0.6 | 20.21% | 34.85% |
| 0.9 | 12.75% | 61.74% |
| 1.0 | 9.31% | 82.38% |

**解釈**: rho（CRNによる相関）が強くなるほど、独立2標本z検定は「有意水準を守る」という意味では
過度に保守的になり（Type I errorが目標5%を大きく下回る＝滅多に「有意」と言わなくなる）、その代償として
**検出力が激減する**（rho=0.9では真に10ptの差があっても約13%しか検出できない）。McNemarは相関が強いほど
むしろ検出力が上がる（同じ状況で最大82%まで改善）。これはBid Managerの懸念（独立仮定が実際より広いCIになる
＝過度に保守的）が理論通りであることを裏付ける。

---

## 4. 数値実験3: 実データ検証（`outsourcing_sim` を実際に実行）

理論・疑似データだけでなく、実際のシミュレーション本体 (`outsourcing_sim.simulate.run_many`) を
段階①と全く同じ条件（`n_trials=80`、同一`base_seed`、`REVERSE_FACTORS=[0.75,1.0,1.25]`）で動かし、
`seed`キーで低/基準/高をペアリングして検証した。

### 4.1 デフォルト設定での7パラメータ一括スイープ（base_seed=777）

```
[alpha] pct(low/base/high)=1.2/7.5/6.2  dLow=-6.2pt dHigh=-1.2pt
    McNemar  low-base: b=0 c=5 z=1.79 sig=False   high-base: b=2 c=3 z=0.00 sig=False
    Naive-z  low-base: z=-1.9555... sig=False     high-base: z=-0.31 sig=False
[k1] pct=8.8/7.5/7.5  ほぼ変化なし、両検定とも非有意
[budget_c0], [budget_c1], [funds_0] pct=7.5/7.5/7.5 で完全に変化なし（b=c=0）
[gamma] pct=3.8/7.5/2.5  dLow=-3.8pt dHigh=-5.0pt  両検定とも非有意
[difficulty_0] pct=7.5/7.5/6.2  変化ごく僅か、両検定とも非有意
```

デフォルト設定（`dominant_leader_pct`が概ね一桁%）では、**7パラメータいずれも統計的に有意な変化は
検出されなかった**（=大半のケースで両検定の結論は一致し、「傾向不明瞭」と判定するのが妥当）。alphaの
low-base比較では、独立z検定が `z=-1.9555`（|z|<1.96で僅かに非有意）、McNemarが `z=1.79`（非有意）と、
判定自体は一致したが数値は異なった。

### 4.2 中庸な基準割合（base pctが17.5%程度）になるよう調整した設定での検証（base_seed=2024）

`alpha=0.9, funds_0=300, budget_c1=40` として `dominant_leader_pct`(base) を17.5%まで引き上げ、
alphaの倍率を変えて相関(`phi`係数、ペアの一致度)とMcNemar/独立z検定の違いを直接測定した。

```
base alpha=0.9, dominant_leader_pct(base) = 17.5%
alpha*0.75=0.675: pct=7.5%  deltaPt=-10.0  phi=-0.01  McNemar z=1.65 sig=False | naive z=-1.93 sig=False
alpha*1.25=1.125: pct=100.0% deltaPt=+82.5 phi=定義不能(片方分散0) McNemar b=66 c=0 z=8.00 sig=True | naive z=19.42 sig=True
alpha*0.5=0.450:  pct=10.0%  deltaPt=-7.5   phi=0.18  McNemar z=1.25 sig=False | naive z=-1.39 sig=False
alpha*1.5=1.350:  pct=100.0% deltaPt=+82.5  同上（相転移で100%に張り付き） McNemar z=8.00 sig=True | naive z=19.42 sig=True
```

**重要な発見**: 私は当初「CRNにより低・基準・高は常に強い正の相関を持つはず」と想定していたが、
実データでは alpha を75%/125%という段階①の実際の摂動幅で動かした場合、**ペアの相関係数(phi)は
ほぼ0（-0.01〜0.18程度）にとどまった**。これはv4ログの説明（「限界が生じるのは、一方の設定が
先に試行を終えてしまった場合」）と整合する。すなわち、alphaのような非線形パラメータを±25%動かすと、
多くのトライアルで序盤から挙動が乖離し、CRNによる乱数共有の恩恵（正の相関）がほとんど残らないケースが
現実に存在する。

この発見は、当初「独立仮定は常に過度に保守的（＝CIが広すぎる）」と単純に結論づけるのが必ずしも
正確ではないことを示す。しかし、だからこそ**相関の符号や強さを事前に仮定するアプローチは危険**であり、
McNemar検定のように**実際のペアデータから相関の影響を自動的に織り込む（相関の存在を仮定しない）
頑健な手法**を採用するのが、実務上もっとも安全で説明可能な選択である。相関が強い場合はMcNemarが
恩恵を享受し、相関がほぼ0の場合はMcNemarは独立2標本検定とほぼ同等の振る舞いをする
（実際、上表のphi≈0のケースでも両者の有意/非有意判定は一致している）。一方で相転移が起きて
片方が100%または0%に張り付くケース（b=66, c=0のような極端な非対称）では、McNemarは
`z=8.00`という明確な有意判定を返し、これは実務上も直感的に正しい（3点中2点で挙動が完全に
変わっている以上、これは疑いなく実質的な効果である）。

### 4.3 実験に使用したPythonスクリプト

実験1〜3のスクリプトは検証のために `product/abm-dashboard/logs/` 配下に一時的に作成し、動作確認後に削除した
（`_v5_experiment1_coverage.py`, `_v5_experiment2_mcnemar.py`, `_v5_experiment3_realdata.py`,
`_v5_experiment3b_allparams.py`, `_v5_experiment3c_correlation.py`。実データ検証は
`outsourcing_sim.params.SimParams` と `outsourcing_sim.simulate.run_many` を直接importして実行した）。

---

## 5. 決定事項（タスクの検証観点4点への回答）

### 5.1 Wald vs Wilson

**Wilson score intervalを採用する。** 理由: §2の実験で、n=80でも p が0〜10%または90〜100%付近では
Wald近似の被覆率が目標95%から最大15pt以上乖離し、かつ7割超のケースで区間が`[0,1]`を逸脱するという
非現実的な結果になることを確認したため。`dominant_leader_pct`は実データ検証(§4)でも一桁%や100%張り付きが
頻発する指標であり、この極端領域での精度はUIの信頼性に直結する。

### 5.2 3点差分の統計的評価: 独立2標本 vs 対応のある検定

**対応のある比率差の検定（McNemar検定、継続性補正あり）を採用する。** 独立2標本z検定
（`SE_diff = sqrt(p1(1-p1)/n1+p2(1-p2)/n2)`）は不採用とする。

- 理由1（理論）: 低・基準・高は同一`base_seed`で実行される対応のあるサンプルであり、独立性の仮定自体が
  そもそも成立しない。
- 理由2（§3の疑似データ実験）: 相関が強い場合、独立2標本検定は過度に保守的になり検出力が激減する
  （rho=0.9で検出力13%まで低下）。
- 理由3（§4の実データ検証）: 実際の相関の強さは一律ではなく（ほぼ0のケースも、強い相関で相転移を
  検出するケースもある）、**相関構造を仮定しないで済むMcNemarの方が頑健**。
- v3で「n=3でのPearson相関」が過剰統計として却下された教訓との違い: あの却下は「3点という
  あまりに少ないデータ点に対して相関係数を計算する」ことがそもそも統計的に無意味だったことが理由。
  今回のMcNemarは3点(低/基準/高)ではなく、**各点n=最大80件のトライアル単位の対応関係**に基づく検定であり、
  標本サイズの妥当性の問題はない。既存の`per_trial`データの`seed`フィールドで機械的にペアリングできる、
  1行で書ける単純な公式であり、複雑さの追加は最小限である。

**採用する具体的な数式**:

個々の点のCI（Wilson score interval, 95%）:
```
p_hat = k / n   (k = dominant_leaderヒット数, n = そのポイントのトライアル数 = sweepNTrials)
z = 1.96
center = (p_hat + z^2/(2n)) / (1 + z^2/n)
half   = (z / (1 + z^2/n)) * sqrt( p_hat*(1-p_hat)/n + z^2/(4n^2) )
CI_low  = max(0, center - half) * 100   [pt]
CI_high = min(1, center + half) * 100   [pt]
```

低vs基準、高vs基準のペア比較（McNemar検定、継続性補正あり）:
```
低配列 lowHits[seed] と 基準配列 baseHits[seed] を seed をキーに突き合わせる
b = count(lowHits[s] === true  && baseHits[s] === false)   # 低のみhit
c = count(lowHits[s] === false && baseHits[s] === true)    # 基準のみhit
if (b + c === 0) z = 0   // 不一致ペアが1つもない = 差の証拠なし
else z = (abs(b - c) - 1) / sqrt(b + c)
有意 ⇔ |z| >= 1.96  (両側5%水準)
```
（高vs基準も同じ式で `highHits` と `baseHits` を使って計算する）

**多重比較補正について**: 7パラメータ×2比較=14件の検定を行うが、Bonferroni等の補正は**採用しない**。
理由: 段階①はテーブル自身の注意書きが明記する通り「上位パラメータを絞り込むための粗いスクリーニング」であり、
最終判断は必ず段階②の精密な組合せ探索で再検証される設計である。この段階で補正をかけて閾値を厳格化すると、
本来有望なパラメータを早期に取りこぼす偽陰性のリスクの方が実害が大きいと判断した。この非補正の方針は
注意書き（§6のUI文言案）に明記し、透明性を確保する。

### 5.3 ラベリング方式（3段階）

Bid Manager AC-A3.2 の要求（3値以上の区別）に対し、既存の`direction`（単調性判定、変更しない）と、
上記McNemar検定の結果を組み合わせた3段階の `confidenceTier` を新設する。

```
isMonotonic = (direction !== "方向が一定しない（試行回数が少なく、乱数ノイズの影響が大きい可能性）")
sigLowBase  = |mcnemarZ(lowHits, baseHits)|  >= 1.96
sigHighBase = |mcnemarZ(highHits, baseHits)| >= 1.96

if (!isMonotonic)                       confidenceTier = "unclear"      // 傾向不明瞭
else if (sigLowBase || sigHighBase)     confidenceTier = "significant"  // 有意な方向性あり
else                                     confidenceTier = "uncertain"   // 傾向はあるが不確実
```

表示文言（日本語、確定案）:

| confidenceTier | バッジ文言 | 補足説明（tooltip/注記） |
|---|---|---|
| `significant` | 「有意な方向性あり」 | 「低vs基準または高vs基準の差が、対応のある比率差の検定（McNemar検定）で統計的に有意でした（p<0.05）。」 |
| `uncertain` | 「傾向はあるが不確実」 | 「3点の並びには方向性が見られますが、この試行数（最大80件）では対応のある比率差の検定で有意差を確認できませんでした。効果がないという意味ではなく、この粗い探索条件では判別できないという意味です。」 |
| `unclear` | 「傾向不明瞭」 | 「低い値・高い値で変化の向きが一致せず、一貫した傾向を読み取れませんでした。」 |

**AC-A5.1への対応**: 上記の`uncertain`/`unclear`の文言は、いずれも明示的に「効果がない」ではなく
「この試行数・条件では判別できない」という表現に統一している。

### 5.4 ソート順・段階②への引き継ぎロジック

- **段階①テーブル本体の表示順（`renderReverseStage1Table`が受け取る`rows`の順序）は変更しない**。
  既存の `rows.sort((a, b) => b.maxAbsDeltaPt - a.maxAbsDeltaPt)` をそのまま維持する。ユーザーが既に
  慣れている「変化幅の大きい順」という並びの一貫性を壊さないため、また確信度は別途バッジ列で
  読み取れるようにするため、ソートキー自体を変える必要はないと判断した。
- **一方、`renderReverseParamChoices()`（段階②のチェックボックス候補選定）は確信度を優先する
  ロジックに変更する。** 理由（AC-A5.2への回答）: 現状は`rows`（=`maxAbsDeltaPt`降順）の先頭4件を
  チェックボックス候補、先頭2件を初期チェック済みとしているため、「変化幅は大きいが実は乱数ノイズ」
  （`uncertain`または`unclear`）なパラメータが段階②に自動的に持ち込まれてしまうリスクがある
  （§4.1で確認した通り、デフォルト設定では変化幅が数ptあっても大半が非有意である）。これを避けるため、
  `renderReverseParamChoices`内で候補選定専用のランキング（`confidenceTier`優先、同ランク内は
  `maxAbsDeltaPt`降順）を別途計算し、テーブル表示順とは独立に使う。

  ```js
  function confidenceRank(row) {
    if (row.confidenceTier === "significant") return 0;
    if (row.confidenceTier === "uncertain") return 1;
    return 2; // "unclear"
  }
  function renderReverseParamChoices(rows) {
    const ranked = [...rows].sort((a, b) => {
      const diff = confidenceRank(a) - confidenceRank(b);
      return diff !== 0 ? diff : b.maxAbsDeltaPt - a.maxAbsDeltaPt;
    });
    const top4 = ranked.slice(0, 4).map((row) => row.parameter);
    const selected = new Set(ranked.slice(0, 2).map((row) => row.parameter));
    // ...以降は既存のまま（top4, selectedの参照先をrowsからrankedに差し替えるのみ）
  }
  ```

  テーブルの見た目の順序とチェックボックス初期選択の順序が一致しないケースが生じうるが、
  これは「テーブルは生の変化幅ランキング、チェックボックスは確信度を加味した推奨」という
  役割の違いとしてUI注記に明記する（§6）。

### 5.5 実装がJSのみで完結するか

**完結する。`app.py` / `test_api.py` の変更は不要。** 根拠は§1.2で確認した通り:
- `TrialResult` は既に `seed` と `final_quadrant` を返している。
- `run_many()` は常に `n_trials` 件を欠落なく返す（早期終了で件数が減ることはない）。
- 低・基準・高の3回の呼び出しは同一`base_seed`を使うため、`seed`をキーにしたペアリングは
  クライアント側の`per_trial`データだけで機械的に行える。
- Wilson score interval・McNemar検定はいずれも四則演算と`Math.sqrt`のみで計算可能。

---

## 6. 実装箇所への指針（Implementer向け、関数レベル）

1. **`dominantLeaderPct` 相当の拡張**: 現在ヒット数だけを比率に変換して捨てているため、
   `seed -> hit(boolean)` のマップも返すよう拡張する（例: `dominantLeaderHits(response, strategy)`を新設し、
   `extractStrategyMetrics`に`dominantHits: Map<seed, boolean>`を追加）。既存の`dominant_leader_pct`計算は
   そのまま流用してよい（同じフィルタ結果から両方を導出する）。
2. **新規ヘルパー関数を追加**:
   - `wilsonScoreInterval(k, n, z = 1.96)` → `{ low, high }`（pt単位、0〜100にクリップ）
   - `mcnemarZ(hitsA, hitsB)`（seedキーのMapを受け取り、共通seedのみ突き合わせてb, cを数え、上記式でzを返す）
3. **`summarizeQuadrantSweep`の拡張**: シグネチャを比率のみ(`low, base, high`)から、
   ヒットマップとnも受け取る形に変更する（例:
   `summarizeQuadrantSweep({ pct: lowPct, hits: lowHits, n: sweepNTrials }, { ...base }, { ...high })`）。
   戻り値に `confidenceTier`, `confidenceLabel`, `confidenceDetail`, `zLowBase`, `zHighBase`,
   `ciLow`, `ciBase`, `ciHigh`（各点のWilson区間）を追加する。既存の `deltaLowPt`, `deltaHighPt`,
   `maxAbsDeltaPt`, `direction` は変更せず維持する。
4. **`runReverseStage1()`の変更点**: `dominantPoints.push(metrics.dominant_leader_pct)` に加えて、
   `dominantHitsPoints.push(metrics.dominantHits)` のように各点のヒットマップも収集し、
   `summarizeQuadrantSweep(...)` 呼び出しに渡す引数を上記の新シグネチャに合わせて変更する。
   ループ回数・呼び出し回数・`sweepNTrials`の算出には一切手を触れない。
5. **`renderReverseStage1Table(rows)`の変更点**: 既存7列は維持しつつ、「傾向」列の隣（または同セル内）に
   確信度バッジ列を1列追加する。バッジの文言・詳細説明は§5.3の表の通り。各%セルに
   `title`属性でWilson 95%CIを併記する（例: `title="95%CI: 4.3–17.0%"`）ことで、列を増やしすぎずに
   individual pointのCIも参照可能にする。
6. **`renderReverseParamChoices(rows)`の変更点**: §5.4のコード例通り、確信度優先の`ranked`配列を
   関数内で計算し、`top4`/`selected`の元データとして使う（`renderReverseStage1Table`側の`rows`順序には
   影響しない）。
7. **注意書き（`reverse-disclaimer`）の追記**（AC-A4.4）: 既存の「粗いランキング」「暫定値」の文言は残しつつ、
   以下を追記する:
   > 「有意な方向性あり」「傾向はあるが不確実」「傾向不明瞭」は、各点の試行結果（最大80件）に基づく
   > 対応のある比率差の検定（McNemar検定、有意水準5%、多重比較補正なし）による目安です。
   > 「不確実」「不明瞭」は効果がないという意味ではなく、この試行数・この粗い探索条件では
   > 統計的に判別できないという意味です。
8. **バックエンド**: `app.py`・`outsourcing_sim/`・`tests/test_api.py` の変更は不要（§5.5）。

### 6.1 影響範囲まとめ

| 関数 | 変更内容 |
|---|---|
| `dominantLeaderPct` / `extractStrategyMetrics` | ヒットのseed別マップも返すよう拡張（既存の戻り値は維持しつつ追加） |
| `summarizeQuadrantSweep` | 引数シグネチャ変更（ヒットマップ・nを追加）、戻り値に信頼区間・有意性・確信度ラベルを追加 |
| `runReverseStage1` | 各点のヒットマップ収集を追加。API呼び出し回数・n_trials上限は無変更 |
| `renderReverseStage1Table` | 確信度バッジ列の追加、各%セルにCIのtooltip追加、注意書き文言の追記 |
| `renderReverseParamChoices` | 確信度優先の候補選定ロジックに変更（テーブル表示順とは独立） |
| `app.py` / `test_api.py` / `outsourcing_sim/` | **変更不要** |

---

## 次工程への申し送り

Implementer向けに、以下を確定仕様として引き継ぐ。

1. **個々の点のCI**: Wilson score interval（式は§5.2参照）。Wald近似は採用しない
   （n=80でも p が極端な領域で被覆率が大きく崩れることを実験1で確認済み）。
2. **低vs基準・高vs基準の有意性判定**: 対応のある比率差の検定（McNemar検定、継続性補正あり、式は§5.2参照）。
   `per_trial`の`seed`フィールドで低・基準・高をペアリングする。独立2標本z検定は使わない
   （実験2・3で、独立仮定は相関の強さに応じて過度に保守的にも、ほぼ妥当にもなり得ることを確認し、
   相関構造を仮定しないで済むMcNemarの方が頑健と判断したため）。有意水準は両側5%（|z|>=1.96）、
   多重比較補正は行わない（理由は§5.2）。
3. **ラベルは3段階**: 「有意な方向性あり」／「傾向はあるが不確実」／「傾向不明瞭」。判定ロジックは
   §5.3の擬似コードの通り、既存の`direction`（単調性）とMcNemarの有意性を組み合わせる。文言は
   「効果なし」ではなく「この試行数では判別できない」という表現を厳守する。
4. **表のソート順は変更しない**（`maxAbsDeltaPt`降順のまま）。ただし段階②のチェックボックス候補
   （`renderReverseParamChoices`の`top4`/`selected`）だけは確信度優先の別ランキングを使う
   （§5.4のコード例通り）。
5. **API呼び出し回数（21回）・n_trials上限（80）は一切変更しない**。すべての計算は既存レスポンスの
   `per_trial`（`seed`, `final_quadrant`）から追加の呼び出しなしで完結する。
6. **バックエンド変更は不要**。`app.py`・`test_api.py`・`outsourcing_sim/`はいずれも変更対象外。
   実装は`index.html`のJSのみで完結する。
7. 詳細な実装箇所・関数シグネチャ変更・影響範囲は§6・6.1を参照のこと。

---

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
