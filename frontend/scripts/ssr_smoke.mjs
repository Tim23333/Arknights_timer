// SSR 冒烟：渲染 App 根组件 + 带数据渲染 OperatorTimeline（合并单行视图）
import { createServer } from "vite";
import { createSSRApp, h } from "vue";
import { renderToString } from "vue/server-renderer";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const server = await createServer({
  root: frontendRoot,
  logLevel: "silent",
  server: { middlewareMode: true },
});
try {
  const { default: App } = await server.ssrLoadModule("/src/App.vue");
  const html = await renderToString(createSSRApp(App));
  for (const text of ["我方操作时间轴", "添加干员行", "敌方列表"]) {
    if (!html.includes(text)) throw new Error(`App 渲染结果缺少: ${text}`);
  }
  console.log("APP_OK", `渲染 ${html.length} 字符`);

  const { default: OperatorTimeline } = await server.ssrLoadModule("/src/components/OperatorTimeline.vue");
  const groups = {
    deploy: [
      { id: "r1", oper: "维什戴尔", actions: [
        { id: "a1", frame: 300, pos: "(5,2)", direction: "上", note: "" },
        { id: "a2", frame: 900, pos: "(3,4)", direction: "右", note: "" },
      ] },
      { id: "r2", oper: "琴柳", actions: [{ id: "a5", frame: null, pos: "", direction: "", note: "" }] },
    ],
    skill: [
      { id: "r3", oper: "维什戴尔", actions: [{ id: "a3", frame: 600, pos: "", direction: "", note: "" }] },
      { id: "r4", oper: "琴柳", actions: [{ id: "a6", frame: 700, pos: "", direction: "", note: "" }] },
    ],
    withdraw: [
      { id: "r5", oper: "维什戴尔", actions: [{ id: "a4", frame: 1200, pos: "", direction: "", note: "" }] },
    ],
  };
  const html2 = await renderToString(createSSRApp({
    render: () => h(OperatorTimeline, {
      groups, fps: 30, pxPerSecond: 12, durationFrames: 7200, playFrame: 450, playing: false,
    }),
  }));
  for (const text of ["维什戴尔", "琴柳", "部署", "技能", "撤退", "F300", "F600", "F1200", "帧空"]) {
    if (!html2.includes(text)) throw new Error(`OperatorTimeline 渲染结果缺少: ${text}`);
  }
  // 合并验证：维什戴尔应只出现一行（row-meta 数量 = 干员数 2）
  const rowCount = (html2.match(/class="row-meta"/g) || []).length;
  if (rowCount !== 2) throw new Error(`合并行数错误: ${rowCount} (期望 2)`);
  console.log("TIMELINE_OK", `合并行数 ${rowCount}, 渲染 ${html2.length} 字符`);
} finally {
  await server.close();
}
