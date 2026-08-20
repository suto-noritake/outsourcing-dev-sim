# v3 Architect Log — Architect

作成者: Architect（私）
日時: 2026-08-20T09:14:07+09:00

## 0. 要約

Bid Managerの v3 AC1〜AC5・実現性評価・Go判断を受領した。Go判断（フロントエンドのみで実装し
`/api/simulate` の契約は変更しない）そのものは妥当と判断し、支持する。

ただし Bid Manager 自身が申し送りで明記している通り、ドラフトの一部（特に AC3.3 の感度分析設計と
AC2.1 のジッター提案）には**ソースコードで裏付けが取れない、あるいは裏付けを取ると危険と分かる主張**
が含まれていた。v2 で低努力ドラフトに実際の事実誤りが見つかった前例があるため、今回も
`outsourcing_sim/model.py` / `simulate.py` / `params.py` / `strategies.py` を全て読んだ上で、
以下の順で確定させる。

1. ソースコード突き合わせによる検証結果（訂正した点を含む）
2. 分析設計の最終確定（四象限分布％・傾向コメント・感度チェック）
3. 散布図再設計の最終確定（Chart.js設定・凡例・ジッター可否）
4. ビジュアルデザイン刷新の最終確定（CSS具体値）
5. 次工程への申し送り

---

## 1. ソースコード検証結果（Bid Manager案の是正）

| 論点 | Bid Manager案 | 検証結果 | 判定 |
|---|---|---|---|
| 四象限の閾値 | `dominant_leader`等4象限、閾値は「技術優位度0」「資金体力5」 | `model.py: quadrant()` → `tech_ok = cap_margin >= 0`, `funds_ok = runway >= runway_threshold(=5.0)`。`simulate.py`で`quadrant(cap_margin, runway)`として呼ばれ、閾値の上書きなし。**既存UIの象限説明文と一致**しており、Bid Manager案もこの前提を踏襲していて問題なし。 | 誤りなし（確認のみ） |
| sigma_noise・k1 を感度チェック対象に選んだこと | 「sigma_noiseとk1の±25%をmean_net_profitに対してスイープ」 | `model.py: credit_cost()` = `k1 * cost_mult(tier) * n * D * noise`、`noise = rng.lognormal(0, sigma_noise)`。**k1は毎ラウンドのコストに線形に効き、他のどの経路にも登場しない**（`capability()`はalphaのみ使用、k1は無関係）。**sigma_noiseは対数正規ノイズの標準偏差**で、`E[noise] = exp(sigma_noise²/2)`となり `sigma_noise`が大きいほどコストの**期待値そのものも**押し上げる（分散が増えるだけではない）。さらに`strategies.py: _expected_cost()`は意思決定時に同じ`exp(sigma_noise²/2)`補正を使っており、`cost_optimal`戦略の選択（tier, n）には影響しない（全候補に同じ係数がかかるだけで argmin が変わらない）ことも確認した。よって両パラメータは`net_profit`に対して**直接的・単調・機械的**な経路を持ち、感度チェック対象として理にかなっている。 | 妥当。対象パラメータの選定は追認する |
| `sigma_noise`が「所要時間」にも影響するという含意（Bid Manager案には明記されていないが要注意） | （直接の記載なし） | `model.py: time_required()`という関数が`sigma_noise`を使って所要時間にノイズを乗せる実装になっているが、**`simulate.py: run_game()`はこの関数を一切呼び出していない**（未使用のデッドコード）。つまり現行シミュレーションにおいて`sigma_noise`が実際に効いてくる経路は**コストのみ**であり、「進行の遅さ」等を暗示する説明文は書かない。 | 新規に発見した事実。UI文言に反映（誤解防止） |
| **AC3.3: 3点のPearson相関係数** | 「low/base/high の3点でPearson rを計算し、相関として提示する」 | **統計的に不健全と判定し、不採用に訂正する。** 3点の相関はデータ点数=3・自由度(df)=n-2=1 であり、両側5%水準で有意になるために必要な臨界値は `t = r/√(1-r²)` の関係から逆算すると **`|r| ≈ 0.997`**（ほぼ完全な直線関係）が必要になる。つまり「r=0.85」のような、一見それらしい数値を出しても統計的裏付けは無いに等しく、むしろ非技術者に誤った精密さの印象を与える（クライアントの「分析があまい」という指摘を、今度は「見かけ倒しの厳密さ」という別の形で再生産するリスクがある）。さらに各点は`n_trials`回の乱数試行の**平均**であり、その平均自体に標準誤差が乗っている状態で3点のrを取ることは、パラメータ変化への感度と乱数由来のばらつきを混同する（タスク指示が懸念していた通り）。 | **誤り・不採用に訂正**。代わりに §2.3 の「低/基準/高の平均純利益＋変化率(%)＋単調性判定」を採用する |
| **AC2.1: ジッター（±0.12）＋不透明度0.85** | 「重なり防止のため座標をランダムに±0.12ずらし、不透明度0.85で描画」 | **ジッターは不採用に訂正する。** 理由は2点。(1) 象限の判定閾値は `capability_margin=0`（縦線）・`funding_runway=5`（横線）という**意味のある実数の境界**であり、`quadrant`は色でエンコードされている。座標を±0.12ずらすと、例えば `capability_margin=0.05`（dominant_leader, 緑）の点が見かけ上 `-0.07`（exit_candidate側）に描画され得る。これは「色（象限）が正しいのに位置が閾値をまたいで見える」という、まさにクライアントが問題視している「散布図が見づらい・信用できない」を助長する。ツールチップで正確な値を確認すれば分かるとはいえ、**パッと見の位置と色が矛盾する**表示は避けるべき。(2) 不透明度0.85は、円が重なっても2〜3個の重なり程度ではほぼ透けて見えず、「散らばりが見えない」というクライアント指摘の解決にならない。**代わりに、座標は一切変更せず、不透明度を0.55まで下げて重なりを色の濃淡で可視化し、加えて象限境界（x=0, y=5）に薄い破線の基準線を描画するプラグインを追加**して「境界に対してどこにいるか」を視覚的に補強する（§3参照）。 | **誤り・不採用に訂正** |
| AC1.2/AC1.3: マーカー形状を別凡例として明示 | 「戦略ごとの形状を凡例に文書化」（Chart.js既定凡例は無効化） | クライアント決定は「四象限パネル（`#quadrant-legend`）のみを凡例の唯一の正とする」なので、**新たに別パネルの凡例を追加するのはクライアント決定に反する**。よって形状の説明は独立した凡例ではなく、**既存の `#quadrant-legend` パネルの中に1行の注記として同居させる**形に訂正する（比較モード時のみ表示）。これにより「凡例は1箇所」を守りつつ AC1.2 の「形状を文書化する」も満たす。 | 解釈を修正（実装方式を確定） |

以上により、Bid Manager案のうち **AC3.3（相関係数の採用）と AC2.1（ジッター＋不透明度0.85）は
不採用/修正**とし、それ以外（AC1.1/AC1.4/AC2.2の形状・ストローク方針/AC3.1/AC3.2の方針/AC4/AC5）
は妥当と判断してそのまま採用する。

---

## 2. 分析設計の最終確定

### 2.1 四象限分布％（AC3.1）— 新規の追加通信なし

`per_trial`（既存レスポンスに既に含まれる）を戦略ごとに集計するだけで算出できる。バックエンド変更不要。

```js
function quadrantDistribution(strategy, perTrial) {
  const rows = perTrial.filter((r) => r.strategy === strategy);
  const total = rows.length;
  const counts = {};
  Object.keys(QUADRANT_LABEL_JA).forEach((q) => { counts[q] = 0; });
  rows.forEach((r) => { counts[r.final_quadrant] = (counts[r.final_quadrant] || 0) + 1; });
  return Object.keys(QUADRANT_LABEL_JA).map((q) => ({
    quadrant: q,
    count: counts[q],
    pct: total ? (counts[q] / total) * 100 : 0
  }));
}
```

**表示（各 strategy-card 内に追加）**: 四象限ラベル＋スウォッチ＋％を横棒（CSS幅で表現、新規チャートは
追加しない）で表示する。

```html
<div class="quadrant-dist">
  <div class="quadrant-dist-title">四象限分布（試行N=<span>{{total}}</span>）</div>
  <!-- 各象限を pct 降順で -->
  <div class="quadrant-dist-row">
    <span class="swatch" style="background:{{color}}"></span>
    <span class="quadrant-dist-label">{{quadrantLabelJa}}</span>
    <div class="quadrant-dist-bar-track">
      <div class="quadrant-dist-bar-fill" style="width:{{pct}}%; background:{{color}};"></div>
    </div>
    <span class="quadrant-dist-pct">{{pct.toFixed(1)}}%</span>
  </div>
</div>
```

### 2.2 傾向コメント（AC3.2）

`quadrantDistribution` の最大％の象限と `aggregates[strategy]` の `bankruptcy_rate` を組み合わせた
ルールベースの1文生成。**因果を断定する表現は避け、observed tendencyの記述に徹する。**

```js
function tendencyCommentary(strategy, distRows, aggregate) {
  const top = distRows.reduce((a, b) => (b.pct > a.pct ? b : a));
  const bkr = aggregate.bankruptcy_rate;
  const label = formatStrategy(strategy);

  if (top.pct < 30) {
    return `${label}は特定の型に偏らず、試行ごとに結果の型が大きく分かれています` +
      `（最多でも${top.pct.toFixed(0)}%）。設定条件に対して結果が安定しにくい戦略と言えます。`;
  }
  const base = {
    dominant_leader: `${label}は試行の${top.pct.toFixed(0)}%が①独走勝ち組型に到達しており、` +
      `技術・資金の両面で優位に立てる傾向が強い設定です。`,
    cash_starved_specialist: `${label}は試行の${top.pct.toFixed(0)}%が②宝の持ち腐れ／燃え尽き型です。` +
      `技術力は足りているのに資金体力が続かない傾向があり、資金繰り面（部分払い・予算係数等）の` +
      `見直し余地があります。`,
    deep_pockets_shallow_skills: `${label}は試行の${top.pct.toFixed(0)}%が③物量型／時間稼ぎ型です。` +
      `資金体力で延命はできていますが、技術力が難易度に追いついていない傾向があります。`,
    exit_candidate: `${label}は試行の${top.pct.toFixed(0)}%が④淘汰予備軍型です。` +
      `技術・資金とも劣勢になりやすく、倒産割合も${(bkr * 100).toFixed(1)}%と${bkr > 0.3 ? "高水準" : "一定水準"}です。`
  };
  return base[top.quadrant];
}
```

これを各 strategy-card に `<p class="tendency-text">` として追加する。

### 2.3 パラメータ感度チェック（AC3.3・修正版）

#### 2.3.1 データ源の選択：スイープ方式を採用する（単一実行内の相関ではない）

タスクで提示された代替案（単一実行の`per_trial`内で seed 由来のばらつきと最終指標の相関を見る方式）
を検討したが、**不採用**とする。理由：`per_trial`内のばらつきは「同一パラメータ・異なる乱数シード」に
起因するものであり、これは「もしパラメータを変えたらどうなるか」という**感度**の問いには答えない。
`sigma_noise`は固定された1つの値でも試行間にばらつきを生むが、そのばらつきから「`sigma_noise`を
上げたら/下げたらどうなるか」を推定することはできない（固定値のもとでの分散と、値そのものを動かした
ときの効果は別物）。したがって、クライアントが求める「パラメータ感度」を答えるには
**実際にパラメータを動かした追加実行（スイープ）が必要**であり、Bid Manager案の「複数回
`/api/simulate` を呼ぶ」という方向性は正しい。誤っていたのは統計処理（Pearson r）の部分のみである。

#### 2.3.2 共通乱数（Common Random Numbers）によるノイズ低減

スイープの3点（低・基準・高）は、**対象パラメータ以外は完全に固定**し、かつ**同一の `base_seed`・
同一の `n_trials`** で呼び出す。同一シード集合（0..n_trials-1）を使い回すことで、乱数由来の
ばらつきの一部を打ち消す（分散低減法としての common random numbers）。ただし完全な対応関係を
保証するものではない点は明記する：本モデルは成功・失敗によって試行ごとの経路が分岐するため、
パラメータ変更で挙動が変わった時点以降は同一シードでも乱数消費列が一致しなくなる。したがって
「厳密なペアリング」ではなく「ばらつきを幾らか抑える工夫」として説明する。

#### 2.3.3 対象パラメータと範囲

- 対象パラメータ: `k1`, `sigma_noise`（§1の検証で妥当性を確認済み）
- 各パラメータについて 基準値×0.75（低）／基準値×1.0（基準）／基準値×1.25（高）の3点
- 範囲クランプ: `sigma_noise` は API 制約 `0 <= sigma_noise <= 2.0` のため、高値が2.0を超える場合は
  2.0にクランプしその旨を表示する。基準値が0の場合はその パラメータのスイープをスキップし、
  「基準値が0のため感度チェックをスキップしました」と表示する。`k1` は `>0` のみ制約なので
  低値がゼロ以下になることはない。

#### 2.3.4 対象戦略とスイープ回数（ガードレール、AC5.3）

- 感度チェックは**フォームで現在選択されている単一の戦略**（比較モードのON/OFFに関わらず
  `strategy` セレクトの値）に対してのみ実行する。3戦略全部を対象にすると
  `2パラメータ × 3点 × 3戦略 = 18回`の追加通信になり非現実的なため。
- `n_trials`は `Math.min(150, 現在のフォームのn_trials)` に固定する（ユーザー入力なし）。
  これにより追加通信は常に **最大 2×3=6回、各回 n_trials<=150** で完結し、
  API の `n_trials<=500` ガードレールに自動的に収まる。
- 実行はオプトイン（ボタン押下）とし、事前に概算所要時間を表示する:
  `estSeconds = mainRun.meta.elapsed_seconds * (sweepNTrials / mainRun.meta.n_trials) * 6`
  （直前に実行したメイン実行の`elapsed_seconds`を実測値として比例配分するだけの簡易見積り）。
  見積りが10秒を超える場合は「メイン実行の試行回数を減らすと感度チェックが速くなります」という
  注記を表示する。

#### 2.3.5 統計処理：% 変化と単調性判定（Pearson rの代替）

```js
function summarizeSweep(low, base, high) {
  const denom = Math.abs(base) > 1e-9 ? Math.abs(base) : 1e-9;
  const deltaLowPct = ((low - base) / denom) * 100;
  const deltaHighPct = ((high - base) / denom) * 100;
  const maxAbsDeltaPct = Math.max(Math.abs(deltaLowPct), Math.abs(deltaHighPct));
  let direction;
  if (high > base && base > low) direction = "増加方向（値を上げると平均純利益が増える傾向）";
  else if (high < base && base < low) direction = "減少方向（値を上げると平均純利益が減る傾向）";
  else direction = "方向が一定しない（試行回数が少なく、乱数ノイズの影響が大きい可能性）";
  return { low, base, high, deltaLowPct, deltaHighPct, maxAbsDeltaPct, direction };
}
```

表として提示: パラメータ名 / 低(-25%)の平均純利益 / 基準の平均純利益 / 高(+25%)の平均純利益 /
傾向 / 最大変化幅(%)。

#### 2.3.6 UIの注釈文言（確定・そのまま実装すること）

パネル見出し: 「パラメータ感度チェック（探索的・簡易版）」

説明文（パネル冒頭に常時表示）:
> 選択中の戦略について、指定パラメータを基準値の75%・100%・125%に変えた3パターンを、
> 同じ試行回数・同じ乱数の開始番号で実行し、平均純利益がどちらの方向にどれくらい振れるかを
> 比較する簡易的なチェックです。3パターンだけの比較のため、相関係数などの統計的検定は
> 行っていません（3点しかない場合は見かけ上ほぼ必ずきれいな相関になってしまい、
> かえって誤った精密さの印象を与えるため、あえて採用していません）。あくまで大まかな
> 傾向をつかむための参考情報としてご利用ください。

実行ボタン横の見積り表示: 「概算所要時間: 約{estSeconds}秒（追加で最大6回のシミュレーションを
実行します。対象戦略: {targetStrategyJa}）」

---

## 3. 散布図再設計の最終確定

### 3.1 データセット構成

戦略ごとに1データセット（比較モードOFF時は1つのみ）。色は象限のみ、形状は戦略のみ。

```js
const strategyPointStyle = {
  conservative: "circle",
  cost_optimal: "triangle",
  adaptive: "rect"
};

function withAlpha(hex, alpha) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function drawScatter(response) {
  const grouped = {};
  response.plot_data.quadrant_points.forEach((point) => {
    grouped[point.strategy] = grouped[point.strategy] || [];
    grouped[point.strategy].push(point);
  });

  const keys = response.meta.compare_strategies ? strategyOrder : Object.keys(grouped);
  const datasets = keys
    .filter((k) => grouped[k] && grouped[k].length)
    .map((strategy) => ({
      label: formatStrategy(strategy), // 凡例は非表示。デバッグ・a11y用に保持するのみ
      data: grouped[strategy].map((p) => ({
        x: p.x, y: p.y, quadrant: p.quadrant, seed: p.seed, strategy: p.strategy
      })),
      pointStyle: strategyPointStyle[strategy] || "circle",
      pointBackgroundColor: grouped[strategy].map(
        (p) => withAlpha(quadrantColors[p.quadrant] || "#6b7280", 0.55)
      ),
      pointBorderColor: "rgba(30, 41, 59, 0.55)", // slate-800 半透明。象限色とのコントラスト用の中立ストローク
      pointBorderWidth: 1.25,
      pointRadius: 5,
      pointHoverRadius: 7,
      pointHoverBorderWidth: 2
      // 注意: x/y は実測値のまま。ジッターは適用しない（理由は§1参照）
    }));

  if (scatterChart) scatterChart.destroy();
  scatterChart = new Chart(document.getElementById("scatter-chart"), {
    type: "scatter",
    data: { datasets },
    plugins: [quadrantThresholdPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }, // AC1.3: #quadrant-legend のみを凡例の正とする
        tooltip: {
          callbacks: {
            label: (context) => {
              const point = context.raw || {};
              return [
                `戦略: ${formatStrategy(point.strategy)}`,
                `シード値: ${point.seed}`,
                `技術優位度: ${Number(point.x).toFixed(2)}`,
                `資金体力: ${Number(point.y).toFixed(2)}`,
                `分類: ${formatQuadrant(point.quadrant)}`
              ];
            }
          }
        }
      },
      scales: {
        x: { title: { display: true, text: "技術優位度 (capability_margin)" } },
        y: { title: { display: true, text: "資金体力 (funding_runway)" } }
      }
    }
  });

  renderQuadrantLegend(response.meta.compare_strategies);
}
```

### 3.2 象限境界の基準線プラグイン（新規、外部依存なし）

Chart.jsのプラグインAPIのみで実装し、`chartjs-plugin-annotation`等の追加CDN依存は導入しない
（既存の Chart.js CDN 依存のみで完結させる）。

```js
const quadrantThresholdPlugin = {
  id: "quadrantThresholds",
  afterDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea) return;
    const xPix = scales.x.getPixelForValue(0);
    const yPix = scales.y.getPixelForValue(5);
    ctx.save();
    ctx.strokeStyle = "rgba(100, 116, 139, 0.6)"; // slate-500
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    if (xPix >= chartArea.left && xPix <= chartArea.right) {
      ctx.beginPath();
      ctx.moveTo(xPix, chartArea.top);
      ctx.lineTo(xPix, chartArea.bottom);
      ctx.stroke();
    }
    if (yPix >= chartArea.top && yPix <= chartArea.bottom) {
      ctx.beginPath();
      ctx.moveTo(chartArea.left, yPix);
      ctx.lineTo(chartArea.right, yPix);
      ctx.stroke();
    }
    ctx.restore();
  }
};
```

### 3.3 凡例（唯一の情報源は `#quadrant-legend`）

`renderQuadrantLegend` を比較モードフラグを受け取るように拡張し、比較モード時のみ形状の説明を
**同じパネル内**に1行追加する（別パネル・別凡例は作らない＝クライアント決定を厳守）。

```js
function renderQuadrantLegend(compareStrategies = false) {
  quadrantLegendEl.innerHTML = "";
  if (compareStrategies) {
    const note = document.createElement("div");
    note.className = "shape-legend-note";
    note.textContent =
      "形状（比較モード時のみ）: ● 保守的　▲ コスト最適　■ 適応型　※色は四象限のみを表します";
    quadrantLegendEl.appendChild(note);
  }
  Object.keys(QUADRANT_LABEL_JA).forEach((quadrant) => {
    const detail = QUADRANT_DETAILS[quadrant];
    const item = document.createElement("div");
    item.className = "quadrant-item";
    item.innerHTML = `
      <div class="quadrant-title"><span class="swatch" style="background:${quadrantColors[quadrant] || "#6b7280"}"></span>${formatQuadrant(quadrant)}</div>
      <div>${detail.meaning}</div>
      <div><strong>示唆:</strong> ${detail.implication}</div>
    `;
    quadrantLegendEl.appendChild(item);
  });
}
```

初期表示（データ未取得時）は `renderQuadrantLegend(false)` を呼ぶ。`strategyColors`変数と、
散布図・ヒストグラムの凡例オブジェクトへの依存は、散布図側では不要になる（ヒストグラムは
戦略ごとの棒グラフのままなので `strategyColors` と `legend: {position:"bottom"}` は維持してよい。
ヒストグラムの凡例は「戦略名」を示すだけで象限色とは無関係なため、クライアント決定
（凡例1本化の対象は**散布図の戦略色**）には抵触しない）。

---

## 4. ビジュアルデザイン刷新の最終確定（AC4）

以下の値をそのまま採用する。CSSカスタムプロパティで一元管理する。

```css
:root {
  --color-bg: #f8fafc;       /* slate-50 */
  --color-panel: #ffffff;
  --color-border: #e2e8f0;   /* slate-200 */
  --color-text: #334155;     /* slate-700 */
  --color-heading: #0f172a;  /* slate-900 */
  --color-muted: #64748b;    /* slate-500 */
  --color-accent: #2563eb;   /* blue-600 */
  --color-accent-hover: #1d4ed8; /* blue-700 */
  --shadow-panel: 0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 10px rgba(15, 23, 42, 0.05);
  --radius-panel: 12px;
  --radius-card: 10px;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Yu Gothic UI", Meiryo,
    Roboto, "Noto Sans JP", sans-serif;
  margin: 0;
  padding: 24px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 14px;
  line-height: 1.6;
}
h1 { font-size: 24px; font-weight: 700; color: var(--color-heading); margin: 0 0 16px; }
h2 {
  font-size: 17px; font-weight: 700; color: var(--color-heading);
  margin: 0 0 12px; padding-left: 10px; border-left: 4px solid var(--color-accent);
}
h3 { font-size: 15px; font-weight: 700; color: var(--color-heading); margin: 0 0 4px; }

.panel {
  border: 1px solid var(--color-border); border-radius: var(--radius-panel);
  padding: 16px; margin-bottom: 16px; background: var(--color-panel);
  box-shadow: var(--shadow-panel);
}
.strategy-card {
  border: 1px solid var(--color-border); border-radius: var(--radius-card);
  padding: 12px; background: #fff; box-shadow: var(--shadow-panel);
}
.metric-label { font-weight: 600; font-size: 12.5px; color: var(--color-heading); }
.metric-label small { font-weight: 400; color: var(--color-muted); }
.metric-value { font-size: 22px; font-weight: 700; color: var(--color-heading); margin-top: 2px; }
.metric-help { font-size: 12px; color: var(--color-muted); margin-top: 2px; line-height: 1.45; }

button {
  border-radius: 8px; border: 1px solid transparent; cursor: pointer;
  font-weight: 600; padding: 8px 14px; font-size: 13px;
}
#run-btn, #compare-btn, #sensitivity-run-btn {
  background: var(--color-accent); color: #fff;
}
#run-btn:hover, #compare-btn:hover, #sensitivity-run-btn:hover { background: var(--color-accent-hover); }
#baseline-btn { background: #fff; border-color: #cbd5e1; color: var(--color-text); }
#baseline-btn:hover { background: #f1f5f9; }

.shape-legend-note { font-size: 12px; color: var(--color-muted); margin-bottom: 4px; }

.quadrant-dist-title { font-size: 12.5px; font-weight: 600; color: var(--color-heading); margin-top: 10px; }
.quadrant-dist-row { display: grid; grid-template-columns: 12px 108px 1fr 44px; align-items: center; gap: 6px; margin-top: 4px; font-size: 12px; }
.quadrant-dist-bar-track { background: #f1f5f9; border-radius: 999px; height: 8px; overflow: hidden; }
.quadrant-dist-bar-fill { height: 100%; border-radius: 999px; }
.tendency-text { font-size: 12.5px; color: var(--color-text); margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--color-border); line-height: 1.5; }

.sensitivity-panel .intro { font-size: 12.5px; color: var(--color-muted); line-height: 1.6; margin-bottom: 8px; }
.sensitivity-table { border-collapse: collapse; width: 100%; font-size: 12.5px; margin-top: 8px; }
.sensitivity-table th, .sensitivity-table td { border: 1px solid var(--color-border); padding: 6px 8px; text-align: right; }
.sensitivity-table th:first-child, .sensitivity-table td:first-child { text-align: left; }
```

その他:
- `.chart-container { height: 400px; }` はそのまま維持（変更不要）。
- モバイル時の `280px` （`@media (max-width: 480px)`）は既に実装済みで AC4.3 を満たしているため、
  **変更不要**（Bid Manager案の記載は現状追認でよい）。
- `strategyColors` はヒストグラムでの戦略識別のために引き続き使用する（散布図では使わない）。

---

## 5. データフロー概要（実装者向けサマリ）

- `/api/simulate` のリクエスト/レスポンススキーマは**一切変更しない**（AC5.1）。
- 通常実行（単一 or 比較）で返る `per_trial` / `aggregates` / `plot_data` から
  §2.1（四象限分布％）・§2.2（傾向コメント）・§3（散布図）を**追加通信なし**で描画する。
  これは既存の `showSummary` / `drawScatter` の拡張として実装する。
- 感度チェック（§2.3）のみ、ユーザーの明示操作をトリガに `/api/simulate` を最大6回追加で呼ぶ。
  既存の `runSimulation` とは独立した関数（例: `runSensitivitySweep()`）として実装し、
  メインのシミュレーション実行フローには影響を与えない。
- `tests/test_api.py` はバックエンドを一切変更しないため無改修で green のまま。

---

## 6. 実装チェックリスト（QA前の自己確認用）

- [ ] 散布図: 色=象限のみ、形状=戦略のみ（比較モード時）、Chart.js既定凡例 `display:false`
- [ ] 散布図: x/yは実測値のまま描画（ジッターなし）、不透明度0.55、境界線プラグイン追加
- [ ] `#quadrant-legend` 以外に凡例パネルを新設していないこと
- [ ] 戦略カードに四象限分布％・傾向コメントが追加されていること（追加通信なし）
- [ ] 感度チェックパネル: オプトイン実行、対象は選択中の単一戦略、n_trials<=150、6回以内
- [ ] 感度チェックの注釈文言（3点のみ・統計的検定は行っていない旨）がそのまま表示されていること
- [ ] `pytest product\abm-dashboard\tests\test_api.py` が無改修のまま green
- [ ] CSSは §4 のトークン・値をそのまま採用（フォントスタックにJP fallbackを含める）

---

## 次工程への申し送り

実装担当へ:

1. 本ログ §1 の是正表を必ず読むこと。特に **Pearson r（AC3.3）と ジッター（AC2.1）は不採用**に
   変更している。Bid Manager案のドラフト値をそのまま実装しないよう注意。
2. 散布図は座標を一切加工しない。「散らばりが見えない」への対策は
   ①不透明度0.55による重なりの濃淡表現、②象限境界（x=0, y=5）の基準線描画、の2点のみで行う。
3. 凡例は `#quadrant-legend` のみ。形状の説明は同パネル内の1行注記として比較モード時のみ追加する
   （別パネルを新設しない）。
4. 感度チェックは新規パネルとして追加し、実行は必ずボタン押下によるオプトインとする
   （ページロード時や通常のシミュレーション実行時に自動発火させない）。
5. バックエンド（`app.py`）・`tests/test_api.py` は無改修。フロントエンド
   （`product/abm-dashboard/static/index.html`）のみを変更すること。
6. 実装完了後は `pytest product\abm-dashboard\tests\test_api.py` を実行して既存回帰が
   green のままであることを確認し、加えてブラウザ上で「通常実行」「3戦略比較」
   「感度チェック実行」の3パターンを手動確認すること。

以上。私は本タスクにおいて、Bid Manager案の統計的誤り（3点でのPearson相関係数の採用、
自由度1では有意水準5%の臨界値が|r|≈0.997になるため実質的に無意味）と、可視化上のリスク
（象限境界をまたぎかねないジッター、重なりを解消できない不透明度0.85）の2点をソースコードと
統計的根拠に基づき是正した。それ以外のBid Manager案（形状エンコーディング・四象限分布％・
傾向コメントの方針・デザイン刷新の方向性・バックエンド無改修方針）は妥当と判断し、そのまま
採用した上で、実装者がそのまま着手できる粒度までChart.js設定・CSS・JS関数を確定した。

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
