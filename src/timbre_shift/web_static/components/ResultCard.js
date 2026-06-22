export function ResultCard() {
  return `<section id="result" class="result-page hidden">
    <div class="result-hero"><h2>生成结果</h2><p id="resultSummary">等待生成</p><div id="resultFacts" class="result-facts"></div></div>
    <div id="resultGrid" class="result-grid">
      <div id="mainPlayerCard" class="player-card"><h3 id="mainPlayerTitle">成品歌曲</h3><audio id="player" controls></audio><div class="button-row"><a id="download" class="download" href="#" download>下载 MP3</a><a id="downloadWav" class="download secondary" href="#" download>下载 WAV</a></div></div>
      <div id="dryVocalCard" class="player-card"><h3>干声人声</h3><audio id="dryVocalPlayer" controls></audio><div class="button-row"><a id="downloadDryVocal" class="download" href="#" download>下载干声 MP3</a><a id="downloadDryVocalWav" class="download secondary" href="#" download>下载干声 WAV</a></div></div>
    </div>
    <div id="scorecard" class="score-grid"></div>
    <div id="resultNotices" class="result-notices"></div>
    <div id="variants" class="variant-grid"></div>
    <details class="details-panel"><summary>调试详情</summary><div id="metrics" class="metrics"></div><div id="nextSteps"></div></details>
    <button class="secondary" id="savePreferenceButton" type="button">保存为该音色默认参数</button>
  </section>`;
}
