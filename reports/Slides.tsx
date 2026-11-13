import React from "react";
import edaSignal from "../outputs/figures/report_eda_signal.png?url";
import seriesGap from "../outputs/figures/report_series_gap.png?url";
import finalExample from "../outputs/figures/report_final_example.png?url";
import monthly from "../outputs/figures/report_monthly.png?url";
import alertSweep from "../outputs/figures/report_alert_sweep.png?url";

const TOTAL = 15;

// 章立て：Ⅰ 結論 → Ⅱ 前提とアプローチ → Ⅲ 結果 → Ⅳ 限界と今後
function Slide({ n, chapter, topic, title, children }: {
  n: number; chapter: string; topic: string; title: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="slide">
      <p className="section">{chapter}<em>{topic}</em></p>
      <h2>{title}</h2>
      <div className="body">{children}</div>
      <span className="page">{n} / {TOTAL}</span>
    </section>
  );
}

const I = "Ⅰ 結論";
const II = "Ⅱ 前提とアプローチ";
const III = "Ⅲ 結果";
const IV = "Ⅳ 限界と今後";

export default function Slides() {
  return (
    <>
      <section className="slide cover">
        <p className="eyebrow">変圧器の油温予測 ｜ PoC報告</p>
        <h1>系列2型の設備では、<br />1時間先の油温予測で誤差を半減でき、<br />急上昇の事前通知にも使える見込み</h1>
        <p className="cover-sub">公開データセットETTを用いた技術検証</p>
        <span className="page">1 / {TOTAL}</span>
      </section>

      <Slide n={2} chapter={I} topic="エグゼクティブサマリー"
        title={<>効く設備では誤差が半減し、急上昇の約9割を1時間前に通知できた。<br />ただし効果は設備次第で、導入前の事前評価が前提になる</>}>
        <table className="matrix">
          <thead><tr><th>問い</th><th>答え</th><th>根拠：ETTm2・1時間先・2018年1〜6月の最終テスト</th></tr></thead>
          <tbody>
            <tr><td>持続予測より<br />当たるか</td><td><span className="badge main">Yes</span>系列2では誤差が約半分</td><td>MAE 0.91 → 0.46で49%減。<br />別期間でも検証時と同程度に改善</td></tr>
            <tr><td>季節や高温でも<br />崩れないか</td><td><span className="badge main">Yes</span>全月・高温時とも改善</td><td>月別の改善幅は39〜56%。<br />高温時の過小予測量は0.81 → 0.40</td></tr>
            <tr><td>急上昇を事前に<br />知らせられるか</td><td><span className="badge main">見込みあり</span>基準次第で使える水準</td><td>検知89%、ただし通知の的中は53%。<br />誤報を1日1件以下に絞ると検知47%</td></tr>
            <tr><td>どの設備でも<br />効くか</td><td><span className="badge ac">No</span>系列1ではほぼ差がない</td><td>同じ構成でも系列1は−1〜4%。<br />負荷の追加・LightGBMも効かなかった</td></tr>
          </tbody>
        </table>
        <p className="callout"><b>ご提案</b>対象設備で持続予測との差を事前評価し、効く設備で1時間先の見通しと急上昇の通知を試行する</p>
      </Slide>

      <Slide n={3} chapter={II} topic="背景と検証範囲"
        title={<>保全判断に役立つかを、<br />精度・頑健性・急上昇・設備差の4つの問いに分けて検証した</>}>
        <div className="cols">
          <div>
            <h3>予測の条件</h3>
            <ul>
              <li>予測時点までに<b>観測済みの値だけ</b>を使う。<br />10:00に11:00を予測するなら、10:15以降は使わない</li>
              <li>比較の基準は<b>持続予測</b>。<br />現在の油温をそのまま将来の値とする</li>
              <li>主な予測時間は<b>1時間先</b></li>
            </ul>
          </div>
          <div>
            <h3>置いた仮定</h3>
            <table>
              <tbody>
                <tr><td className="key">設備の数</td><td>4ファイルは2系列×2つの観測間隔。<br /><b>独立した設備は実質2台</b></td></tr>
                <tr><td className="key">単位・負荷</td><td>単位、負荷6項目の意味は未確認。<br />記録値のまま扱う</td></tr>
                <tr><td className="key">急上昇・高温</td><td>学習期間の90パーセンタイル以上。<br />実験用の基準で、安全基準ではない</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <p className="note foot">データ出典：https://github.com/zhouhaoyi/ETDataset　追加データは使用していない</p>
      </Slide>

      <Slide n={4} chapter={II} topic="EDA"
        title={<>油温は直前の値でほぼ決まり、負荷との関係は弱い。<br />日周期の強さは系列で3倍ほど異なる</>}>
        <img className="figure" src={edaSignal} alt="油温と負荷の相関、ETTm1とETTm2の日内パターン" />
        <div className="cols">
          <p><span className="hl">示唆1</span>　持続予測が強い基準になる。<br />まず油温の履歴を主な入力にし、<br />負荷は追加して効くかを個別に確かめる</p>
          <p><span className="hl">示唆2</span>　日周期の強いETTm2では、<br />過去数日分の油温の履歴が効く可能性がある</p>
        </div>
      </Slide>

      <Slide n={5} chapter={II} topic="アプローチ"
        title={<>持続予測を基準に、説明しやすい線形モデルへ入力を1つずつ足し、<br />効いたものだけを残して最終テストに進んだ</>}>
        <div className="flow">
          <div><h3>① 入力の探索</h3><p>ETTh1・1時間先で、油温の直近値・負荷・過去の同時刻を1つずつ追加</p></div>
          <div><h3>② 設備への展開</h3><p>4ファイルで同じ方法を比べ、どの設備で効くかを確認</p></div>
          <div><h3>③ 条件の絞り込み</h3><p>効果の大きいETTm2で、予測時間と履歴の長さを比較</p></div>
          <div><h3>④ 最終テスト</h3><p>選んだ構成を2018年の期間で1回だけ評価</p></div>
        </div>
        <div className="cols">
          <div>
            <h3>主モデル：Ridge回帰</h3>
            <ul>
              <li>どの入力が効いたかを説明しやすい</li>
              <li>油温の履歴同士は相関が強いため、<br />L2正則化で重みを安定させる</li>
            </ul>
          </div>
          <div>
            <h3>比較用のモデル</h3>
            <ul>
              <li><b>持続予測</b>：学習不要の基準</li>
              <li><b>LightGBM</b>：非線形な関係で<br />精度が上がるかを確認</li>
            </ul>
          </div>
        </div>
        <table>
          <thead><tr><th>試した入力・モデル</th><th>結果</th><th>判断</th></tr></thead>
          <tbody>
            <tr><td>油温の直近値＋1〜7日前の同時刻</td><td>ETTh1で持続予測をわずかに上回った</td><td><span className="badge main">採用</span></td></tr>
            <tr><td>直近1〜7日分の連続した油温</td><td>ETTm2で最も誤差が小さかった</td><td><span className="badge main">採用</span></td></tr>
            <tr><td>負荷6項目の各種の入れ方、LightGBM</td><td>どの入れ方でも誤差が増えた</td><td><span className="badge sub">不採用</span></td></tr>
          </tbody>
        </table>
      </Slide>

      <Slide n={6} chapter={II} topic="評価設計"
        title={<>未来の情報が混ざらないよう正解の時刻で分割し、<br />基準値は学習期間で、通知の基準は検証期間で決めた</>}>
        <table>
          <thead><tr><th>区分</th><th>正解の時刻</th><th>決めたこと</th><th className="r">ETTm2の件数</th></tr></thead>
          <tbody>
            <tr><td className="key">学習</td><td>2016年7月〜2017年6月</td><td>Ridgeの重み、急上昇・高温の基準</td><td className="r">34,365</td></tr>
            <tr><td className="key">検証</td><td>2017年7月〜12月</td><td>入力・履歴の長さ、通知の基準</td><td className="r">17,664</td></tr>
            <tr className="best"><td className="key">最終テスト</td><td>2018年1月〜6月26日</td><td>何も決めず、評価だけに使う</td><td className="r">16,976</td></tr>
          </tbody>
        </table>
        <table>
          <thead><tr><th>指標</th><th>意味と使い方</th></tr></thead>
          <tbody>
            <tr><td className="key">MAE</td><td>外れた幅の平均。主指標としてモデルの比較に使った</td></tr>
            <tr><td className="key">平均過小予測量</td><td>実測を下回った幅の平均。保全では低めに外す方が危険なため加えた</td></tr>
            <tr><td className="key">検知率・誤報</td><td>予測した上昇幅で通知したときに、急上昇を何件捉え、何件空振りしたか</td></tr>
          </tbody>
        </table>
      </Slide>

      <Slide n={7} chapter={III} topic="設備による違い"
        title={<>油温の履歴の効果は設備で大きく異なり、<br />系列2でのみ持続予測を大きく上回った</>}>
        <img className="figure" src={seriesGap} alt="4系列の3時間先MAE：持続予測とRidgeの比較" />
        <div className="cols">
          <p>系列1に直近7日分・1時間先の最終構成を<br />そのまま当てても、MAEの改善は<br />検証で4.2%、最終テストで1.2%にとどまった</p>
          <p>差の原因は特定できていない。<br />日周期の強さが候補。<br /><b>導入前に設備ごとの事前評価が必要</b></p>
        </div>
        <p className="note">図：3時間先、検証期間は2017年7〜12月。Ridgeの入力は直近3点と1〜7日前の同時刻の油温。系列ごとに学習した。</p>
      </Slide>

      <Slide n={8} chapter={III} topic="効かなかったもの"
        title={<>負荷6項目の追加もLightGBMも、<br />油温の履歴だけを使うRidgeを上回らなかった</>}>
        <div className="cols l">
          <table className="num">
            <thead><tr><th>ETTh1・1時間先・検証4,416件</th><th>MAE</th></tr></thead>
            <tbody>
              <tr><td>持続予測</td><td>0.5351</td></tr>
              <tr><td>Ridge：直近の油温3点</td><td>0.5378</td></tr>
              <tr><td>　＋予測時点の負荷6項目</td><td>0.5630</td></tr>
              <tr><td>　＋10時間前のHULL・MULL</td><td>0.5495</td></tr>
              <tr className="best"><td>　＋1〜7日前の同時刻の油温</td><td>0.5304</td></tr>
              <tr><td>LightGBM：入力は最良と同じ</td><td>0.5626</td></tr>
            </tbody>
          </table>
          <div>
            <h3>負荷で減った低め外れの多くは、<br />予測が全体に高めになった効果</h3>
            <p>3時間先で負荷を加えると、急上昇時の<br />過小予測量は2.53 → 1.94に減ったが、<br />全体のMAEは悪化した</p>
            <p>予測に<b>+0.26を一律に足すだけでも</b><br /><b>2.27</b>まで減った</p>
            <p>他の系列でも、負荷の追加で<br />MAEは改善しなかった</p>
            <p className="note">+0.26は、急上昇以外での高め外れが負荷ありと同じになるよう検証データで決めた値。負荷の意味が分かれば、効く入れ方がある可能性は残る。</p>
          </div>
        </div>
      </Slide>

      <Slide n={9} chapter={III} topic="最終テスト"
        title={<>ETTm2の1時間先では、<br />条件を選んだ期間とは別の期間でも誤差が持続予測の約半分になった</>}>
        <div className="cols r">
          <div>
            <h3>検証で履歴の長さを選んだ</h3>
            <table className="num">
              <thead><tr><th>Ridgeの入力</th><th>検証MAE</th></tr></thead>
              <tbody>
                <tr><td>直近1日・96点</td><td>0.4539</td></tr>
                <tr className="best"><td>直近7日・672点</td><td>0.4458</td></tr>
                <tr><td>直近14日・1,344点</td><td>0.4507</td></tr>
              </tbody>
            </table>
          </div>
          <div>
            <h3>最終テスト：2018年1〜6月・16,976件</h3>
            <table className="num">
              <thead><tr><th>方法</th><th>MAE</th><th>RMSE</th><th>持続予測比</th></tr></thead>
              <tbody>
                <tr><td>持続予測</td><td>0.9108</td><td>1.2789</td><td>—</td></tr>
                <tr><td>Ridge・1日分</td><td>0.4675</td><td>0.6797</td><td>−48.7%</td></tr>
                <tr className="best"><td>Ridge・7日分</td><td>0.4608</td><td>0.6662</td><td>−49.4%</td></tr>
              </tbody>
            </table>
          </div>
        </div>
        <p>検証期間のMAE 0.4458に対し、最終テストは0.4608。<br /><b>期間が変わっても誤差の水準はほぼ変わらなかった</b></p>
        <div className="kpis foot">
          <div className="kpi"><span>MAE・主指標</span><b>0.91 → 0.46</b><em>持続予測 → Ridge・7日分で49%減</em></div>
          <div className="kpi"><span>1日分の履歴でも</span><b>−48.7%</b><em>改善の大半が得られ、扱うデータが少なくて済む</em></div>
          <div className="kpi"><span>正則化の強さ alpha</span><b>0.01〜10で差なし</b><em>検証MAEの差は0.0001未満で、設定に頑健</em></div>
        </div>
      </Slide>

      <Slide n={10} chapter={III} topic="季節・高温での頑健性"
        title={<>夏を含むどの月でも誤差は約4〜6割減り、<br />油温が高いときの低め外れも半分になった</>}>
        <div className="cols" style={{ gridTemplateColumns: "700px 1fr", gap: 28 }}>
          <img className="figure" src={monthly} alt="月ごとのMAE" />
          <div>
            <h3>高温時：油温が学習期間の上位10%以上</h3>
            <table className="num">
              <thead><tr><th>最終テスト・605件</th><th>MAE</th><th>過小予測量</th></tr></thead>
              <tbody>
                <tr><td>持続予測</td><td>1.29</td><td>0.81</td></tr>
                <tr className="best"><td>Ridge・7日分</td><td>0.62</td><td>0.40</td></tr>
              </tbody>
            </table>
            <p style={{ marginTop: 14 }}>最も暑い2017年7月、平均油温43でも<br />改善は51%</p>
            <p className="note">高温の基準は油温43.0以上で、学習期間の90パーセンタイル。検証期間の2,296件でもMAEは1.33 → 0.53。7〜12月は条件選びに使った期間のため参考値。</p>
          </div>
        </div>
      </Slide>

      <Slide n={11} chapter={III} topic="急上昇時の誤差"
        title={<>急上昇への追従は大きく改善したが、<br />上昇の立ち上がりではなお低めに外れ、予測値±1.0の幅にも収まりにくい</>}>
        <img className="figure" src={finalExample} alt="最終テスト期間の2日間の実測と予測" />
        <div className="kpis">
          <div className="kpi"><span>急上昇時の平均過小予測量</span><b>2.77 → 0.89</b><em>持続予測 → Ridge・7日分で68%減</em></div>
          <div className="kpi"><span>実測が予測値±1.0に収まった割合</span><b>全体 89%</b><em>±1.0は、検証期間で実測の9割が収まる幅として決めた</em></div>
          <div className="kpi"><span>急上昇時に±1.0に収まった割合</span><b className="ac">57%</b><em>42%は実測が予測値+1.0を超えた</em></div>
        </div>
        <p className="note">図は最終テスト期間のうち急上昇が最も多かった2018年4月8〜9日。急上昇は1時間の上昇幅が学習期間の90パーセンタイル約+1.76以上で、1,829件。</p>
      </Slide>

      <Slide n={12} chapter={III} topic="急上昇の事前通知"
        title={<>予測上昇幅で通知すると、急上昇の約9割を1時間前に捉えられた。<br />ただし誤報との兼ね合いで、基準は運用側の許容量に合わせて選ぶ必要がある</>}>
        <div className="cols" style={{ gridTemplateColumns: "640px 1fr", gap: 28 }}>
          <img className="figure" src={alertSweep} alt="検証期間における通知基準ごとの検知率と的中率" />
          <div>
            <h3>検証で決めた基準を、最終テストに当てた結果</h3>
            <table className="num">
              <thead><tr><th>基準</th><th>検知率</th><th>的中率</th><th>誤報</th></tr></thead>
              <tbody>
                <tr><td className="key">A：+0.95</td><td><b>89%</b></td><td>53%</td><td>1日8.3件</td></tr>
                <tr><td className="key">B：+2.00</td><td><b>47%</b></td><td>84%</td><td>1日0.9件</td></tr>
              </tbody>
            </table>
            <ul className="note-list">
              <li>A：検証で的中率50%以上を保つ中で、検知率が最大の基準</li>
              <li>B：検証で誤報が1日1件以下の中で、検知率が最大の基準</li>
              <li>基準の選定も評価も15分ごとの判定で数えた。各時刻で、1時間前の予測上昇幅が基準以上なら通知、実際の1時間の上昇幅が+1.76以上なら急上昇とした。最終テストの急上昇は1,829件、177日間</li>
              <li>持続予測は上昇を予測しないため通知できない。ETTh1では同じ方法で検知0件</li>
            </ul>
          </div>
        </div>
      </Slide>

      <Slide n={13} chapter={IV} topic="工夫・設計判断"
        title={<>結論を過大に見せないよう、<br />比較条件の統一と、基準・期間の事前固定を徹底した</>}>
        <table className="matrix">
          <thead><tr><th>判断</th><th>内容</th><th>理由</th></tr></thead>
          <tbody>
            <tr><td>基準を固定</td><td>常に持続予測と比べる</td><td>自己相関0.99の油温で、現状より当たるかを示すため</td></tr>
            <tr><td>条件を統一</td><td>入力は1つずつ足し、学習行・評価行をそろえる</td><td>入力の効果だけを比べるため</td></tr>
            <tr><td>リーク防止</td><td>急上昇の基準は学習期間、通知の基準は検証期間で決める</td><td>評価期間の情報を混ぜないため</td></tr>
            <tr><td>テストは1回</td><td>2018年の期間は選んだ構成の評価だけに使う</td><td>選択の偏りで結果を良く見せないため</td></tr>
            <tr><td>保全目線の指標</td><td>過小予測量・検知・誤報も測る</td><td>低めに外す方が保全上は危険なため</td></tr>
          </tbody>
        </table>
        <p className="note foot">再現：python -m athena_task.ridge --dataset ETTm2 --sixty-minutes --week-recent --final-test ／ python -m athena_task.limits</p>
      </Slide>

      <Slide n={14} chapter={IV} topic="限界"
        title={<>通知性能や誤差幅は追加で検証できたが、<br />設備の少なさと、実機の基準との対応づけは残っている</>}>
        <table className="matrix">
          <thead><tr><th>限界</th><th>追加検証の結果</th><th>残る課題</th></tr></thead>
          <tbody>
            <tr><td>通知性能</td><td><span className="badge main">確認</span>基準Aで、最終テストの検知89%・的中率53%</td><td>誤報は1日8件と多い。急上昇の基準は統計的な仮置きで、実機の警報基準と対応していない</td></tr>
            <tr><td>予測値の誤差幅</td><td><span className="badge main">確認</span>予測値±1.0に実測の89%が収まり、幅の目安として使える</td><td>急上昇時は57%しか収まらない。上昇時は幅を広げる必要がある</td></tr>
            <tr><td>設備による差</td><td><span className="badge sub">一部</span>系列1は同じ構成でも改善1〜4%</td><td>設備は実質2台。差の原因は未特定</td></tr>
            <tr><td>データの意味</td><td><span className="badge ac">未検証</span>—</td><td>単位、負荷6項目の意味、外気温が不明</td></tr>
          </tbody>
        </table>
      </Slide>

      <Slide n={15} chapter={IV} topic="今後の方針"
        title={<>次は実設備のデータで、<br />効く設備の見極めと、実機の警報基準での通知性能を確かめたい</>}>
        <div className="flow">
          <div><h3>① 要件の確認</h3><p>警報基準、必要な先行時間、許容できる誤報数を決める</p></div>
          <div><h3>② 事前評価</h3><p>対象設備の過去データで、持続予測との差を測る</p></div>
          <div><h3>③ 改善</h3><p>外気温の追加、急上昇時の低め外れの補正、上昇時の誤差幅の拡大</p></div>
          <div><h3>④ 試行運用</h3><p>見通しと通知を担当者に出し、判断に役立つか確かめる</p></div>
        </div>
        <div className="cols">
          <div>
            <h3>試行に進む目安</h3>
            <p>夏を含む過去データで、<br />持続予測よりMAEと過小予測量が<br />明確に下がること。系列2は該当</p>
          </div>
          <div>
            <h3>通知に使う目安</h3>
            <p>運用側が決めた誤報の許容量のもとで、<br />必要な検知率を満たすこと。<br />系列2は基準Aで検知89%・的中率53%</p>
          </div>
        </div>
        <p className="callout"><b>ご相談</b>夏期を含む対象設備の過去データ、外気温データ、現行の警報しきい値の共有</p>
      </Slide>
    </>
  );
}
