"use client";

// 命理小站页。
// 交互流：生日表单 → POST /api/fortune/reading（命盘确定性计算 + 知识库 RAG + 模型解读）
// 解读失败时接口仍返回命盘（reading 为 null）——命盘永远可用。
// 黄历在页面加载时拉取一次。
import { useEffect, useState } from "react";
import Nav from "./Nav.jsx";
import PageHeading from "./PageHeading.jsx";
import AnimatedCardGrid from "./AnimatedCardGrid.jsx";

const API = process.env.NEXT_PUBLIC_API_BASE_URL;

const SHICHEN = [
  ["子时 23:00-00:59", 23], ["丑时 01:00-02:59", 1], ["寅时 03:00-04:59", 3],
  ["卯时 05:00-06:59", 5], ["辰时 07:00-08:59", 7], ["巳时 09:00-10:59", 9],
  ["午时 11:00-12:59", 11], ["未时 13:00-14:59", 13], ["申时 15:00-16:59", 15],
  ["酉时 17:00-18:59", 17], ["戌时 19:00-20:59", 19], ["亥时 21:00-22:59", 21],
];

const WUXING = ["木", "火", "土", "金", "水"];
const WUXING_COLORS = { 木: "#34a853", 火: "#ea4335", 土: "#f9ab00", 金: "#9aa0a6", 水: "#4285f4" };

const READING_FIELDS = [
  ["personality", "性格特质"],
  ["strengths", "优势"],
  ["weaknesses", "短板"],
  ["career", "事业与学习"],
  ["relationships", "人际关系"],
  ["advice", "建议"],
];

export default function FortuneView() {
  const [birthDate, setBirthDate] = useState("2000-01-01");
  const [hour, setHour] = useState(12);
  const [gender, setGender] = useState(null); // 1男 0女 null未知
  const [result, setResult] = useState(null); // { chart, reading, reading_error }
  const [almanac, setAlmanac] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/api/fortune/almanac`)
      .then((res) => res.ok && res.json())
      .then((data) => data && setAlmanac(data))
      .catch(() => {});
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API}/api/fortune/reading`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          birth_date: birthDate,
          birth_hour: hour,
          gender: gender ?? null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `查询失败：${res.status}`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const chart = result?.chart;

  return (
    <AnimatedCardGrid className="dashboard-grid">
      <article className="hero-stage panel-full">
        <Nav />
        <PageHeading
          title="命理小站"
          subtitle="生辰八字 · 五行十神 · 今日黄历（仅供传统文化参考）"
        />
      </article>

      <article className="panel panel-half lab-panel card">
        <div className="panel-heading">
          <p className="section-kicker">输入区</p>
          <h3>你的生日</h3>
        </div>
        <form className="fortune-form" onSubmit={handleSubmit}>
          <label htmlFor="birth-date">公历生日</label>
          <input
            id="birth-date"
            type="date"
            value={birthDate}
            min="1900-01-01"
            max="2100-12-31"
            onChange={(e) => setBirthDate(e.target.value)}
            required
          />
          <label htmlFor="birth-hour">出生时辰</label>
          <select id="birth-hour" value={hour} onChange={(e) => setHour(Number(e.target.value))}>
            {SHICHEN.map(([label, value]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <label>性别（用于排大运）</label>
          <div className="fortune-gender">
            {[
              ["男", 1],
              ["女", 0],
              ["不填", null],
            ].map(([label, value]) => (
              <button
                key={label}
                type="button"
                className={"gender-btn" + (gender === value ? " active" : "")}
                onClick={() => setGender(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {error && <p className="lab-error">{error}</p>}
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "排盘中…" : "开始排盘解读"}
          </button>
        </form>
      </article>

      <article className="panel panel-half lab-panel card">
        <div className="panel-heading">
          <p className="section-kicker">今日黄历</p>
          <h3>{almanac?.date || "加载中…"}</h3>
        </div>
        {almanac ? (
          <div className="almanac-body">
            <p className="almanac-lunar">{almanac.lunar_text}</p>
            <p className="almanac-ganzhi">
              干支：{almanac.ganzhi.year}年 {almanac.ganzhi.month}月 {almanac.ganzhi.day}日
            </p>
            <p className="almanac-label">宜</p>
            <div className="almanac-tags">
              {almanac.yi.slice(0, 8).map((t) => (
                <span key={t} className="almanac-tag yi">{t}</span>
              ))}
            </div>
            <p className="almanac-label">忌</p>
            <div className="almanac-tags">
              {almanac.ji.slice(0, 8).map((t) => (
                <span key={t} className="almanac-tag ji">{t}</span>
              ))}
            </div>
            <p className="almanac-extra">
              冲：{almanac.chong} · 煞：{almanac.sha} · 值神：{almanac.zhi_xing}
            </p>
          </div>
        ) : (
          <p className="digest-empty">黄历加载失败，稍后刷新试试</p>
        )}
      </article>

      {chart && (
        <article className="panel panel-full card">
          <div className="panel-heading">
            <p className="section-kicker">命盘</p>
            <h3>八字四柱</h3>
          </div>
          <div className="pillar-table">
            <div className="pillar-head">
              <span>柱</span><span>干支</span><span>五行</span><span>天干十神</span><span>地支藏干十神</span>
            </div>
            {chart.pillars.map((p) => (
              <div key={p.name} className="pillar-row">
                <span className="pillar-name">{p.name}</span>
                <span className="pillar-ganzhi">{p.ganzhi}</span>
                <span>{p.wuxing}</span>
                <span>{p.shishen_gan}</span>
                <span>{p.shishen_zhi}</span>
              </div>
            ))}
          </div>
          <div className="chart-chips">
            <span className="almanac-tag yi">日主 {chart.day_master}（{chart.day_master_wuxing}）</span>
            <span className="almanac-tag yi">生肖 {chart.shengxiao}</span>
            <span className="almanac-tag yi">星座 {chart.xingzuo}</span>
            <span className="almanac-tag yi">纳音 {chart.day_nayin}</span>
            {chart.wangshuai && <span className="almanac-tag yi">日主{chart.wangshuai}</span>}
            {chart.dayun && (
              <span className="almanac-tag ji">
                {chart.dayun.start_year}岁{chart.dayun.start_month}月起运
              </span>
            )}
          </div>
          <div className="wuxing-bars">
            {WUXING.map((w) => {
              const n = chart.wuxing_stats[w] || 0;
              return (
                <div key={w} className="wuxing-row">
                  <span className="wuxing-name">{w}</span>
                  <span className="wuxing-track">
                    <span
                      className="wuxing-fill"
                      style={{ width: `${(n / 8) * 100}%`, background: WUXING_COLORS[w] }}
                    />
                  </span>
                  <span className="wuxing-count">{n}</span>
                </div>
              );
            })}
          </div>
        </article>
      )}

      {result?.reading && (
        <article className="panel panel-full card">
          <div className="panel-heading">
            <p className="section-kicker">AI 解读</p>
            <h3>基于命理知识库生成</h3>
          </div>
          <div className="reading-body">
            {READING_FIELDS.map(([key, label]) => (
              <div key={key} className="reading-block">
                <h4>{label}</h4>
                <p>{result.reading[key]}</p>
              </div>
            ))}
          </div>
        </article>
      )}

      {result?.reading_error && (
        <article className="panel panel-full card">
          <p className="lab-error">解读生成失败（{result.reading_error}）。命盘计算结果不受影响。</p>
        </article>
      )}

      {!chart && !loading && (
        <article className="panel panel-full card">
          <p className="digest-empty">输入生日，查看你的八字命盘与 AI 解读。</p>
        </article>
      )}

      <article className="panel panel-full card">
        <p className="fortune-disclaimer">
          本页内容基于传统命理文化的程式化计算与生成，仅供文化娱乐参考，不构成任何人生决策建议。
        </p>
      </article>
    </AnimatedCardGrid>
  );
}
