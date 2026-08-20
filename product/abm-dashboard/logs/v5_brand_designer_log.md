# v5 Brand Designer Log — Brand Designer

作成者: Brand Designer（私）
日時: 2026-08-20T13:05:47.500+09:00
対象: `product/abm-dashboard/static/index.html`

## 0. 前提と進め方

私はこの依頼を **Operate モード** のUI設計として扱った。  
このセッションでは追加ヒアリングの往復ができないため、私は以下だけを根拠に判断を固定した。

- ユーザーブリーフ
- `PRODUCT.md`（今回、明示ブリーフと既存資料から私が新規整理）
- `README.md`
- `docs/DESIGN.md`
- `product/abm-dashboard/README.md`
- `product/abm-dashboard/logs/v5_bid_manager_log.md`
- `product/abm-dashboard/static/index.html` 全体

私は `index.html` や `app.py` を変更していない。今回は**ブランド言語の確定だけ**を行う。

---

## 1. 現状把握

### 1.1 私が確認した情報構造

私は `index.html` を最後まで読み、画面構造を以下の順で把握した。

1. **シミュレーション条件**  
   19の主要入力（うち18件が数値+レンジ、1件が戦略セレクト）と、初期化・実行・3戦略比較ボタン
2. **集計結果サマリー**  
   戦略ごとのカード、主要メトリクス、四象限分布、傾向コメント
3. **感度チェック（探索的・簡易版）**
4. **独走勝ち組型への逆算（2段階）**  
   段階① 影響度ランキング → 段階② 組み合わせ探索
5. **四象限散布図**
6. **生存ラウンド数ヒストグラム**

私は、今回のリデザインでこの情報アーキテクチャを絶対に崩さないと決めた。

### 1.2 現行UIの良い点

私は現行UIに、以下の強みがあると判断した。

- 1ページで完結しており、分析の流れが追いやすい
- パラメータ説明文が丁寧で、日本語化の努力が活きている
- `panel` / `strategy-card` / `reverse-calc-card` / `sensitivity-table` など、部品の粒度はすでに揃っている
- 四象限の概念説明と凡例が分離されており、分析ツールとして誠実

### 1.3 現行UIの弱い点

私は、見た目が「ダサい」と言われた理由を、単純な色味ではなく**視覚ルールの未確定さ**にあると判断した。

- slate / blue 系トークンは無難だが、**この製品固有の判断画面らしさ**がない
- `h2` の青い左線、ブラウザ標準寄りのスライダー、全面同じ濃度の白カードにより、**どこが主・どこが補助かの強弱が弱い**
- テーブル、注記、ステータス、バッジ候補の語彙が未定義で、段階①/②や「暫定/注意/参照」の優先度差が見た目で十分に立っていない
- `small` が説明・注意・進捗・注記に広く使われており、**補足文の階層が混線**している
- レスポンシブ配慮がほぼチャート高さだけなので、表や長い説明の扱いに設計意図がまだない

結論として、私は「少し整った既存SaaS風UI」では足りず、**分析根拠を読むための“調査資料としての静けさ”** を与える必要があると判断した。

---

## 2. 私が採用したデザイン方向

### 2.1 候補として洗った7方向

私は、利用者の文化圏（経営判断、受託開発、分析資料、比較表、仮説検証）から、以下の7方向を短く洗った。
なお、方向選定のコンセプトロールはこの環境では**外部 challenger なしの簡易実行**になったため、私は自前の grounded candidate 7案だけで判断を固定している。

1. **取締役会向けメモ** — 端正だが、操作UIとしてはやや静的すぎる  
2. **PMO統制ボード** — 状態管理には強いが、数理分析の知的な重心が弱い  
3. **マーケット端末 / クオンツ画面** — データ密度は高いが、今回の説明文量にはやや硬すぎる  
4. **機関投資家向けリサーチ・ドシエ** — 数字・注記・比較・注意書きを同時に美しく整理しやすい  
5. **監査バインダー / デューデリジェンス資料** — 誠実だが、少し守りに寄りすぎる  
6. **工業計測機のコンソール** — 入力部品の説得力は出るが、説明文と表に冷たすぎる  
7. **状況室のミッションボード** — 強いが、今回の製品にはドラマが過剰

### 2.2 採用方向

私は **4. 機関投資家向けリサーチ・ドシエ** を採用する。

理由は明確で、今回の製品は「派手なAIダッシュボード」ではなく、**経営層と実務担当者が、仮説をその場で動かしながら判断を下すための証拠画面**だからである。

私はこの方向で、以下を狙う。

- 一覧で見た瞬間に「分析のための道具」だと分かる
- 説明文・注記・表・チャートが、同じ紙面言語で統一される
- 主要アクションは強いが、画面全体は騒がない
- “暫定値”“参考値”“注意”“確からしさ” が見た目で整理される

### 2.3 方向の一文定義

私はこのUIを、**「意思決定会議にそのまま持ち込める、インタラクティブな調査報告書」** として設計する。

---

## 3. デザイン原則

私は以下の原則で全コンポーネントを統一する。

1. **主役はデータと判断**  
   色は装飾ではなく、操作・状態・分類のために使う。
2. **信頼感は“薄いグレーの多用”ではなく、秩序で出す**  
   見出し、注記、表、補助文の格付けを明確にする。
3. **入力UIは“実験機材”として扱う**  
   19入力はこの製品の中核なので、スライダーと数値欄の質感を上げる。
4. **注意書きは罰ゲームの赤字ではなく、読ませる補足枠にする**  
   解析の限界を、脅しではなく誠実さとして見せる。
5. **可読性が先、ブランドはその中に滲ませる**  
   目立つのはCTAではなく、整理された証拠である。

---

## 4. 確定したデザイン言語

### 4.1 カラー戦略

私はページ全体を **Restrained** で固定する。  
面の大半はミストグレー + 白 + インクネイビーで構成し、**アクセント色は主操作と選択状態に限定**する。  
彩度の高い色は、意味のある箇所（ボタン、フォーカス、グラフ系列、警告/成功）にだけ使う。

また、利用シーンを「日中の会議室・デスクトップブラウザ・長文読解あり」とみなし、**ライトテーマ**を採用する。

### 4.2 実装用CSSカスタムプロパティ

私は、Implementer が既存 `:root` を置き換えやすいよう、現行トークン名をできる限り踏襲しつつ拡張した。

```css
:root {
  /* surface */
  --color-bg: #eef2f6;
  --color-bg-subtle: #f7f9fb;
  --color-panel: #ffffff;
  --color-panel-muted: #f8fafc;
  --color-border: #d6dfe8;
  --color-border-strong: #b7c4d3;
  --color-text: #243241;
  --color-heading: #0f1b2d;
  --color-muted: #5d6b7b;
  --color-subtle: #7b8794;

  /* brand action */
  --color-accent: #3154ff;
  --color-accent-hover: #2847d8;
  --color-accent-active: #1f38b5;
  --color-accent-soft: #e7ecff;
  --color-focus-ring: rgba(49, 84, 255, 0.24);

  /* semantics */
  --color-info: #0e7490;
  --color-info-soft: #e3f3f7;
  --color-success: #167c55;
  --color-success-soft: #e5f4ec;
  --color-warning: #8f5a00;
  --color-warning-soft: #fff3de;
  --color-error: #c53d46;
  --color-error-soft: #fdecee;

  /* data viz */
  --color-quadrant-1: #138a5b; /* ① 独走勝ち組型 */
  --color-quadrant-2: #c27a12; /* ② 宝の持ち腐れ／燃え尽き型 */
  --color-quadrant-3: #2b6ef2; /* ③ 物量型／時間稼ぎ型 */
  --color-quadrant-4: #c5424b; /* ④ 淘汰予備軍型 */
  --color-strategy-conservative: #5b4bdb;
  --color-strategy-cost-optimal: #0f8b83;
  --color-strategy-adaptive: #c9651e;
  --color-gridline: rgba(36, 50, 65, 0.12);

  /* controls */
  --color-input-bg: #ffffff;
  --color-input-border: #c8d3de;
  --color-input-border-hover: #9eb1c5;
  --color-input-border-focus: #3154ff;
  --color-slider-track: #dce4ee;
  --color-slider-fill: #3154ff;
  --color-slider-thumb: #ffffff;
  --color-table-head-bg: #edf2f8;
  --color-row-alt: #f9fbfd;
  --color-row-hover: #eef4ff;
  --color-note-bg: #f4f8fc;
  --color-note-border: #d9e5f2;

  /* badges */
  --color-badge-neutral-bg: #eef2f7;
  --color-badge-neutral-text: #445469;
  --color-badge-neutral-border: #d5dee8;
  --color-badge-info-bg: #e7ecff;
  --color-badge-info-text: #2447d5;
  --color-badge-info-border: #cbd6ff;
  --color-badge-success-bg: #e5f4ec;
  --color-badge-success-text: #16664a;
  --color-badge-success-border: #c0e1cf;
  --color-badge-warning-bg: #fff3de;
  --color-badge-warning-text: #8f5a00;
  --color-badge-warning-border: #f1d6a5;
  --color-badge-danger-bg: #fdecee;
  --color-badge-danger-text: #a8333b;
  --color-badge-danger-border: #f5c6cd;

  /* typography */
  --font-family-ui: "Inter", "Segoe UI", "Yu Gothic UI", "Hiragino Sans", Meiryo, "Noto Sans JP", sans-serif;
  --font-family-mono: "Cascadia Mono", "SFMono-Regular", Consolas, monospace;
  --font-size-2xs: 0.75rem;      /* 12px */
  --font-size-xs: 0.8125rem;     /* 13px */
  --font-size-sm: 0.875rem;      /* 14px */
  --font-size-md: 0.9375rem;     /* 15px */
  --font-size-lg: 1rem;          /* 16px */
  --font-size-xl: 1.125rem;      /* 18px */
  --font-size-2xl: 1.375rem;     /* 22px */
  --font-size-3xl: 1.875rem;     /* 30px */
  --font-size-metric: 1.75rem;   /* 28px */
  --line-height-tight: 1.3;
  --line-height-body: 1.55;
  --line-height-loose: 1.7;
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  /* spacing */
  --space-1: 0.25rem;   /* 4px */
  --space-2: 0.5rem;    /* 8px */
  --space-3: 0.75rem;   /* 12px */
  --space-4: 1rem;      /* 16px */
  --space-5: 1.25rem;   /* 20px */
  --space-6: 1.5rem;    /* 24px */
  --space-8: 2rem;      /* 32px */
  --space-10: 2.5rem;   /* 40px */
  --space-12: 3rem;     /* 48px */

  /* shape and depth */
  --radius-panel: 1rem;       /* 16px */
  --radius-card: 0.875rem;    /* 14px */
  --radius-control: 0.625rem; /* 10px */
  --radius-badge: 999px;
  --border-width: 1px;
  --border-width-strong: 2px;
  --shadow-panel: 0 1px 2px rgba(15, 23, 42, 0.04), 0 10px 24px rgba(15, 23, 42, 0.06);
  --shadow-raised: 0 8px 20px rgba(15, 23, 42, 0.08);
  --shadow-focus: 0 0 0 3px rgba(49, 84, 255, 0.24);

  /* layout */
  --page-padding: 1.5rem;  /* 24px */
  --panel-gap: 1.25rem;    /* 20px */
  --panel-padding: 1.25rem;/* 20px */
  --card-padding: 1rem;    /* 16px */
  --control-height: 2.5rem;/* 40px */
  --table-cell-y: 0.625rem;/* 10px */
  --table-cell-x: 0.75rem; /* 12px */
}
```

### 4.3 タイポグラフィスケール

私は、プロダクトUIとして**1ファミリー運用**に固定する。  
表示フォントは `Inter` 優先だが、実装コストを増やしたくない場合はシステムフォールバックだけでも成立するようにしている。

| 用途 | サイズ | 太さ | 行間 | 判断 |
|---|---:|---:|---:|---|
| ページタイトル `h1` | 30px | 700 | 1.2 | 製品名は堂々と見せるが、ヒーロー的にはしない |
| パネル見出し `h2` | 18px | 700 | 1.35 | 現行より明快、ただし過度に大きくしない |
| カード見出し `h3` | 16px | 600 | 1.4 | 情報ブロックの局所見出し |
| 本文 / 入力 / セル本文 | 15px | 400〜500 | 1.55 | 読み疲れを避ける基準サイズ |
| ラベル / テーブル見出し / 補助見出し | 13px | 600 | 1.45 | 多数のUIラベルを揃える基準 |
| 補足文 / 注記 / ステータス | 13px | 400 | 1.55 | `small` を全てこのレイヤーに統一 |
| バッジ / マイクロ注釈 | 12px | 700 | 1.3 | 最小サイズ。これ未満は禁止 |
| 主要メトリクス値 | 28px | 700 | 1.15 | 戦略カードの数値を“読む対象”として立てる |

追加指定:

- 数値は `font-variant-numeric: tabular-nums;` を適用する
- 見出しに display font は使わない
- 日本語本文は letter-spacing をいじらない
- 現行の `body 14px` は **15pxへ引き上げ** る

### 4.4 余白・グリッド・密度

私はこの画面を「高密度だが息苦しくない」状態に置く。

| 項目 | 確定値 |
|---|---|
| body 余白 | 24px（<=768px: 16px、<=480px: 12px） |
| パネル間隔 | 20px |
| パネル内パディング | 20px（<=768px: 16px） |
| カード内パディング | 16px |
| フォームグリッド gap | 12px |
| 数値入力とレンジの縦gap | 6px |
| actions 行 gap | 8px |
| メトリクスブロック間 | 8px〜12px |
| テーブルセル余白 | 縦10px / 横12px |
| 注記ボックス余白 | 12px〜14px |

私の判断は以下。

- パネルは多いので、**外側の余白で整理し、内側は詰めすぎない**
- 説明文が長いので、カード内パディングは 12px ではなく 16px を確保する
- 表は文字を縮めるのではなく、必要なら横スクロールで守る

### 4.5 角丸・境界線・影

私は角丸を「親しみ」ではなく**秩序の柔らかさ**として使う。

- パネル: 16px
- カード: 14px
- 入力 / ボタン: 10px
- バッジ: pill
- 境界線: 基本 1px、強調のみ 2px
- 影: `--shadow-panel` を基本値とし、**影よりボーダーで構造を見せる**

補足:

- 現行の破線区切りは、私は**“未完成感”が強い**と判断した。  
  区切り線は原則として通常の 1px 実線に寄せる。
- 強い立体感やグラデーションは不要。  
  この製品で信頼を作るのは、ガラス感ではなく整理である。

---

## 5. コンポーネント方針

### 5.1 パネル / カード

私は `.panel` を**調査レポートの章**として扱う。

- 背景: `--color-panel`
- 外周: `1px solid --color-border`
- 角丸: `--radius-panel`
- 影: `--shadow-panel`
- 見出し `h2`: **左青線は廃止**。代わりに、余白と太さで階層を出す
- パネル内の補足文は `--color-muted`、必要な注意書きだけ `--color-note-bg` / `--color-warning-soft` に上げる

`.strategy-card` / `.reverse-calc-card` / `.reverse-reco-card` は一段軽いサーフェスにする。

- 背景: `--color-panel-muted`
- 枠線: `--color-border`
- 角丸: `--radius-card`
- 影: 基本は最小限、hover 演出は不要

### 5.2 ボタン

私はボタンを「主操作」「補助操作」の2系統で固定する。

#### Primary

- 対象: `#run-btn`, `#compare-btn`, `#sensitivity-run-btn`, `#reverse-stage1-run-btn`, `#reverse-stage2-run-btn`
- 高さ: 40px 以上
- 背景: `--color-accent`
- 文字: 白
- 枠線: なし
- hover: `--color-accent-hover`
- active: `--color-accent-active`
- focus: `--shadow-focus`
- 影: `--shadow-raised` は主ボタンのみに限定

#### Secondary

- 対象: `#baseline-btn`, 「この設定をフォームに反映」など補助操作
- 背景: 白 or `--color-panel-muted`
- 文字: `--color-heading`
- 枠線: `1px solid --color-input-border`
- hover: `--color-accent-soft` を薄く使う
- disabled: 背景 `--color-bg-subtle`、文字 `--color-subtle`、枠線 `--color-border`

追加指定:

- ボタン角丸は全て 10px
- ラベルは 14px / 600
- CTA は多いが、**主操作だけがアクセント色**を持つ

### 5.3 スライダー `input[type="range"]`

私は今回、スライダーを最重要コンポーネントの1つとみなす。  
理由は、この製品の体験価値が「触りながら読む」ことにあるからだ。

- トラック高さ: 6px
- トラック背景: `--color-slider-track`
- 有効範囲の塗り: `--color-slider-fill`
- サム: 18px 円形
- サム背景: 白
- サム外周: 2px `--color-slider-fill`
- hover: サムを 20px 相当に見せる（ほんの少し拡大）
- focus: 3px `--color-focus-ring`

運用指示:

- `accent-color` 任せではなく、可能なら track / thumb を明示的に整える
- 数値入力欄とレンジは**同格の40px高**で揃える
- ラベル → 数値欄 → スライダーの順は維持しつつ、縦方向の間を 6px で統一する

### 5.4 数値入力 / セレクト

- 高さ: 40px
- 背景: 白
- 枠線: `--color-input-border`
- 通常文字: `--color-text`
- hover 枠線: `--color-input-border-hover`
- focus 枠線: `--color-input-border-focus`
- focus ring: `--shadow-focus`
- 角丸: 10px
- フォント: 14px〜15px

私は、入力欄を“ただのフォーム”ではなく、**精度を持って数値をいじる器具**に見せる。

### 5.5 テーブル（感度表 / 段階①ランキング）

私はテーブルを「箱の集合」ではなく、**比較のための譜面**として設計する。

- 文字サイズ: 本文 13px、見出し 13px / 600
- ヘッダー背景: `--color-table-head-bg`
- ヘッダー文字: `--color-heading`
- 行背景: 白ベース、必要なら `--color-row-alt` の弱いゼブラ
- hover 行: `--color-row-hover`
- 外周枠は維持、**セルごとの濃い罫線は弱める**
- 数値列は右揃え + `tabular-nums`
- セル余白: 縦10px / 横12px

段階①ランキングのための追記:

- 今後追加される「方向の信頼度」列は、**テキスト+バッジの併用**前提
- `maxAbsDeltaPt` は数値自体を太字にしすぎず、**方向ラベルと確からしさの方を先に読ませる**
- 表の下の注意書きは、単なる灰色小文字ではなく**注記ボックス**扱いにする

### 5.6 バッジ / ラベル

私は汎用バッジを先に定義しておく。  
Architect が並行設計している「有意 / 不明瞭」表示は、この語彙に乗せればよい。

**共通仕様**

- 高さ: 24px
- padding: 左右 10px
- 角丸: pill
- フォント: 12px / 700
- 枠線: 1px
- 色だけでなく文字を必ず入れる

**バリアント**

- `badge--info`  
  用途: プレビュー、補足状態、参照情報  
  背景 `--color-badge-info-bg` / 文字 `--color-badge-info-text`
- `badge--success`  
  用途: 方向性あり、好ましい状態  
  背景 `--color-badge-success-bg` / 文字 `--color-badge-success-text`
- `badge--warning`  
  用途: 暫定、解釈注意、ばらつき大  
  背景 `--color-badge-warning-bg` / 文字 `--color-badge-warning-text`
- `badge--danger`  
  用途: エラー、重大注意、破綻系  
  背景 `--color-badge-danger-bg` / 文字 `--color-badge-danger-text`
- `badge--neutral`  
  用途: 未評価、保留、一般タグ  
  背景 `--color-badge-neutral-bg` / 文字 `--color-badge-neutral-text`

### 5.7 ステータス / 注意 / エラー

私は `small` を1種類の見た目で済ませない。

#### 通常補足

- 13px
- `--color-muted`
- 背景なし

#### 進捗・概算時間・軽い状態表示

- 13px
- 背景 `--color-note-bg`
- 枠線 `--color-note-border`
- 角丸 10px
- padding 10px 12px

#### 注意書き / 解析限界の説明

- 背景 `--color-warning-soft`
- 文字 `--color-text`
- 枠線 `1px solid #f1d6a5`
- 左に 3px の warning accent を置いてよい

#### エラー表示

- 背景 `--color-error-soft`
- 文字 `--color-error`
- 枠線 `1px solid #f5c6cd`
- padding 12px 14px
- `white-space: pre-wrap` は維持

### 5.8 グラフ / 凡例

私はグラフを「飾り」ではなく、**証拠の第2本文**として扱う。

#### 四象限散布図

- 点色は四象限色を継続使用
- 点の不透明度は 55〜65%
- 点の境界線はインク系 1.25〜1.5px
- 閾値線は `--color-gridline` より一段強い中立色で破線
- tooltip 背景は `--color-heading`、文字は白

#### ヒストグラム

- 系列色は  
  `conservative = --color-strategy-conservative`  
  `cost_optimal = --color-strategy-cost-optimal`  
  `adaptive = --color-strategy-adaptive`
- 凡例位置は現行踏襲でよいが、文字サイズは 12〜13px に揃える

#### 凡例カード

- `quadrant-item` は小さな白カードではなく、`--color-panel-muted` に寄せる
- swatch は 10〜12px
- タイトル行は 13px / 700
- 説明文は 13px / 400

---

## 6. レスポンシブ・可読性・アクセシビリティ

私は、レスポンシブとアクセシビリティを「後で足すもの」ではなく、今回のブランド仕様に含めて固定する。

### 6.1 レスポンシブ

- `<= 960px`: サマリーカード・逆算候補グリッドは 1列化を許容
- `<= 768px`: body 16px余白、panel 16px padding
- `<= 640px`: `h1 26px`, `h2 17px`, chart 高さ 320px
- `<= 480px`: chart 高さ 280px、body 12px余白
- テーブルは**フォントを潰さず、横スクロール許容**

### 6.2 可読性の下限

- 本文最小: 15px
- ラベル / 表本文 / 注記: 13px
- 最小文字サイズ: 12px（バッジ・ごく小さい補足のみ）
- クリック/タップ対象: 40px 高さ以上

### 6.3 コントラストと非色依存

- 本文コントラストは **4.5:1 以上**
- 大きい見出し・太字数値は **3:1 以上**
- focus ring は背景上で明確に視認できること
- 段階①の信頼度表示は、**色だけでなくテキストとバッジ形状を併用**
- 比較モードの散布図は、現行どおり**形状差**を維持する

---

## 7. 私の最終判断

私は今回、既存の「slate/blueを少し整えたUI」から、**“調査報告書として信頼できる分析ダッシュボード”** へ重心を移した。

私が特に重要だと考えるのは次の4点である。

1. **背景色よりも階層設計がブランドになること**
2. **スライダーと数値欄の質感が、製品の手触りを決めること**
3. **段階①/②や注意書きの格付けを、色と余白で読ませること**
4. **チャート色は意味に結び、主ボタン色とは役割を分けること**

---

## 次工程への申し送り

### Implementer向け確定仕様

- 情報構造・DOM順・機能配置は変えない
- 既存 `:root` を、本ログのトークン群に置換・拡張する
- `h2` の左アクセント線は廃止し、余白と太さ主体の見出しへ移行する
- `body` 基準文字サイズは **14px → 15px**
- `panel` は白、`strategy-card` / `reverse-calc-card` は一段軽い `panel-muted`
- 主ボタンだけを `--color-accent` 系で塗り、補助ボタンは白+境界線に戻す
- スライダーはブラウザ標準感を減らし、**6px track / 18px thumb / 40px入力高**を守る
- テーブルは `13px`, `tabular-nums`, `table-head-bg`, 弱いゼブラ, hover 行を採用する
- 今後追加される「方向の信頼度」表示は、`badge--success / --warning / --neutral` を基本に組む
- 注意書き・概算時間・エラーを同じ `small` 見た目で済ませず、**note / warning / error の3層**に分ける
- 四象限色は以下で固定:  
  ① `#138A5B` / ② `#C27A12` / ③ `#2B6EF2` / ④ `#C5424B`
- 戦略色は以下で固定:  
  conservative `#5B4BDB` / cost_optimal `#0F8B83` / adaptive `#C9651E`

私はこの仕様で、実装後の画面が「受託開発の分析ツール」として十分にプロフェッショナルで、かつ読みやすい状態になると判断する。
