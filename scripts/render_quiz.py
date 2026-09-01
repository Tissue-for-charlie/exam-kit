#!/usr/bin/env python3
"""finals-prepper Phase 4b: 渲染复习题 HTML（交互答题 + 一键批改 + 掌握度报告）。

用法: python render_quiz.py <资料目录>
读取 .final_prep/questions.json 和 knowledge_skeleton.json（拿 kc_id -> 标签映射）。
输出 <课程名>-复习题.html。客观题前端自动批改，主观题折叠参考答案。
"""
import argparse
import html
import json
import os
import re

from html_common import page

TYPE_NAMES = {
    "choice": "单选题",
    "multi": "多选题",
    "tf": "判断题",
    "fill": "填空题",
    "short": "简答题",
    "calc": "计算题",
    "essay": "论述题",
}
SUBJECTIVE = {"short", "calc", "essay"}

QUIZ_CSS = """
.q { position: relative; }
.q-head { font-weight: 600; margin-bottom: 4px; }
.q-no { color: var(--accent); margin-right: 4px; }
.q-type { font-size: 12px; color: var(--muted); margin-left: 6px; font-weight: 400; }
.q-text { margin: 8px 0; }
.q-opts { margin: 6px 0; }
.opt { display: block; margin: 5px 0; padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.opt:hover { background: #f5f3ec; }
.opt-letter { font-weight: 600; margin-right: 4px; }
.fill-in { border: none; border-bottom: 1.5px solid var(--accent); background: #f7f5ee;
  padding: 2px 6px; margin: 0 3px; min-width: 80px; font-size: 14px; outline: none; }
.q-feedback { margin-top: 10px; padding: 10px 14px; border-radius: 8px; font-size: 14px; }
.q-result { font-weight: 600; margin-bottom: 4px; }
.ok { color: #2e7d32; }
.bad { color: var(--must); }
.pts { color: var(--muted); font-weight: 400; margin-left: 6px; }
.q-explain { color: #4a4a44; }
.q-correct { border-left: 4px solid #4caf50; }
.q-wrong { border-left: 4px solid var(--must); }
.submit-bar { position: sticky; bottom: 0; background: #fffdf7; border-top: 1px solid var(--line);
  padding: 12px 0; margin-top: 24px; text-align: center; }
.btn { background: var(--accent); color: #fff; border: none; padding: 10px 28px; border-radius: 8px;
  font-size: 15px; cursor: pointer; }
.btn:hover { background: #0e4a83; }
.report { margin-top: 26px; }
.report h2 { font-size: 18px; }
.score-box { font-size: 22px; font-weight: 600; }
table.kc { width: 100%; border-collapse: collapse; margin-top: 10px; }
table.kc th, table.kc td { border: 1px solid var(--line); padding: 8px 10px; font-size: 13.5px; text-align: left; }
table.kc th { background: #f6f4ec; }
.weak { color: var(--must); font-weight: 600; }
.bar { height: 8px; background: #e9e6dc; border-radius: 4px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); }
.bar i.weak { background: var(--must); }
"""


def _fmt_answer(q):
    t = q["type"]
    a = q["answer"]
    if t == "choice":
        i = a if isinstance(a, int) else int(a)
        return f"{chr(65 + i)}. {q['options'][i]}"
    if t == "multi":
        return "、".join(f"{chr(65 + i)}. {q['options'][i]}" for i in a)
    if t == "tf":
        return "正确" if a else "错误"
    if t == "fill":
        return "、".join(a) if isinstance(a, list) else str(a)
    return str(a)


def _render_question(q, num):
    qid = q["id"]
    t = q["type"]
    type_name = TYPE_NAMES.get(t, t)
    src = q.get("source", "generated")
    src_tag = (f'<span class="tag tag-original">原题</span>' if src == "original"
               else f'<span class="tag tag-generated">AI 生成</span>')
    src_ref = f'<span class="src-ref">{html.escape(q.get("source_ref", ""))}</span>' if q.get("source_ref") else ""

    lines = [f'<div class="card q" data-q="{qid}" data-type="{t}" '
             f'data-kc="{q.get("kc_id", "")}" data-points="{q.get("points", 0)}">']
    lines.append(f'<div class="q-head"><span class="q-no">{num}.</span>{src_tag}'
                 f'<span class="q-type">{type_name}</span>{src_ref}</div>')

    if t == "fill":
        # 把题干里的 ___ 替换成输入框
        idx = [0]
        def repl(m):
            i = idx[0]
            idx[0] += 1
            return f'<input class="fill-in" data-q="{qid}" data-blank="{i}" autocomplete="off">'
        qtext = re.sub(r"_{3,}", repl, html.escape(q["question"]))
        lines.append(f'<div class="q-text">{qtext}</div>')
    else:
        lines.append(f'<div class="q-text">{html.escape(q["question"])}</div>')

    if t in ("choice", "multi"):
        itype = "radio" if t == "choice" else "checkbox"
        lines.append('<div class="q-opts">')
        for i, o in enumerate(q["options"]):
            lines.append(f'<label class="opt"><input type="{itype}" name="{qid}" value="{i}"> '
                         f'<span class="opt-letter">{chr(65 + i)}.</span>{html.escape(o)}</label>')
        lines.append("</div>")
    elif t == "tf":
        lines.append(f'<div class="q-opts"><label class="opt"><input type="radio" name="{qid}" value="true"> 正确</label>'
                     f'<label class="opt"><input type="radio" name="{qid}" value="false"> 错误</label></div>')
    elif t in SUBJECTIVE:
        ans = q.get("answer") or "（无参考答案）"
        lines.append(f'<details class="selftest no-print"><summary>查看参考答案</summary>'
                     f'<div class="selftest-a">{html.escape(ans)}</div></details>')

    lines.append('<div class="q-feedback" style="display:none">'
                 '<div class="q-result"></div><div class="q-explain"></div></div>')
    lines.append("</div>")
    return "\n".join(lines)


def render(quiz: dict) -> str:
    course = quiz.get("course") or "课程"
    parts = [
        f'<h1 class="course-title">{html.escape(course)}</h1>',
        '<div class="course-sub">复习题 · 客观题点选后一键批改，主观题折叠参考答案</div>',
        '<div class="card toc no-print"><b>章节</b><ul>',
    ]
    num = 0
    for ch in quiz["chapters"]:
        label = ch.get("label") or ch["id"]
        parts.append(f'<li><a href="#{ch["id"]}">{html.escape(label)}</a></li>')
    parts.append("</ul></div>")

    for ch in quiz["chapters"]:
        label = ch.get("label") or ch["id"]
        parts.append(f'<h2 class="chapter" id="{ch["id"]}">{html.escape(label)}</h2>')
        for q in ch.get("questions", []):
            num += 1
            parts.append(_render_question(q, num))

    parts.append('<div class="submit-bar no-print">'
                 '<button class="btn" onclick="submitQuiz()">提交批改</button></div>')
    parts.append('<div class="report no-print" id="report" style="display:none"></div>')
    return "\n".join(parts)


QUIZ_JS = r"""
const QUIZ = __QUIZ_JSON__;

function norm(s){
  s = (s==null?'':String(s)).trim().toLowerCase();
  s = s.replace(/[\uff01-\uff5e]/g, c => String.fromCharCode(c.charCodeAt(0)-0xfee0));
  s = s.replace(/[\u3000\u3002\uff0c\u3001\uff1b\uff1a\uff1f\u201c\u201d\uff08\uff09]/g,'');
  return s;
}
function findQ(qid){
  for(const ch of QUIZ.chapters){
    const q = ch.questions.find(x=>x.id===qid);
    if(q) return q;
  }
  return null;
}
function fmtAnswer(q){
  const a=q.answer;
  if(q.type==='choice') return String.fromCharCode(65+(typeof a==='number'?a:parseInt(a)))+'. '+q.options[typeof a==='number'?a:parseInt(a)];
  if(q.type==='multi') return a.map(i=>String.fromCharCode(65+i)+'. '+q.options[i]).join('、');
  if(q.type==='tf') return a?'正确':'错误';
  if(q.type==='fill') return Array.isArray(a)?a.join('、'):String(a);
  return String(a);
}
function submitQuiz(){
  let total=0, max=0;
  const kc={};
  document.querySelectorAll('.q[data-type]').forEach(card=>{
    const qid=card.dataset.q, type=card.dataset.type;
    const points=parseInt(card.dataset.points)||0;
    const kcid=card.dataset.kc;
    const q=findQ(qid);
    if(!q) return;
    let correct=false;
    if(type==='choice'||type==='tf'){
      const sel=card.querySelector('input:checked');
      correct = sel && sel.value===String(q.answer);
    } else if(type==='multi'){
      const sel=[...card.querySelectorAll('input:checked')].map(i=>parseInt(i.value)).sort((a,b)=>a-b);
      const ans=[...q.answer].sort((a,b)=>a-b);
      correct = JSON.stringify(sel)===JSON.stringify(ans);
    } else if(type==='fill'){
      const inputs=[...card.querySelectorAll('input.fill-in')].sort((a,b)=>(a.dataset.blank|0)-(b.dataset.blank|0));
      const user=inputs.map(i=>norm(i.value));
      const ans=(q.answer||[]).map(a=>norm(a));
      correct = user.length===ans.length && user.every((u,i)=>u===ans[i]);
    } else {
      return;
    }
    total += correct?points:0; max += points;
    kc[kcid]=kc[kcid]||{score:0,max:0};
    kc[kcid].score += correct?points:0; kc[kcid].max += points;
    const fb=card.querySelector('.q-feedback');
    fb.style.display='block';
    fb.querySelector('.q-result').innerHTML = correct
      ? '<span class="ok">&#10003; 正确</span><span class="pts">+' + points + ' 分</span>'
      : '<span class="bad">&#10007; 错误</span><span class="pts">正确答案：' + fmtAnswer(q) + '</span>';
    fb.querySelector('.q-explain').innerHTML =
      (q.explanation?('<b>解析：</b>'+q.explanation+'<br>'):'') +
      (q.pitfall?('<b>易错：</b>'+q.pitfall):'');
    card.classList.add(correct?'q-correct':'q-wrong');
  });
  renderReport(total,max,kc);
}
function renderReport(total,max,kc){
  const el=document.getElementById('report');
  const kcMap=QUIZ.kcMap||{};
  let html='<h2 class="chapter">掌握度报告</h2>';
  html+='<div class="card"><div class="score-box">客观题得分：'+total+' / '+max+' 分</div></div>';
  html+='<div class="card"><table class="kc"><tr><th>知识点</th><th>得分</th><th>掌握度</th></tr>';
  const rows=Object.entries(kc).sort((a,b)=>((a[1].score/a[1].max)-(b[1].score/b[1].max)));
  for(const [kid,v] of rows){
    const pct=Math.round(v.score/v.max*100);
    const label=kcMap[kid]||kid;
    const weak=pct<60;
    html+='<tr><td>'+(weak?'<span class="weak">'+label+'</span>':label)+'</td>'
        +'<td>'+v.score+' / '+v.max+'</td>'
        +'<td><div class="bar"><i class="'+(weak?'weak':'')+'" style="width:'+pct+'%"></i></div>'+pct+'%</td></tr>';
  }
  html+='</table></div>';
  if(Object.keys(kc).length===0) html+='<div class="card muted">本题集没有客观题，无法自动统计掌握度。</div>';
  el.innerHTML=html; el.style.display='block';
  el.scrollIntoView({behavior:'smooth'});
}
"""


def main():
    ap = argparse.ArgumentParser(description="渲染复习题 HTML")
    ap.add_argument("root", help="资料目录")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    fp = os.path.join(root, ".final_prep")

    with open(os.path.join(fp, "questions.json"), encoding="utf-8") as f:
        quiz = json.load(f)

    # kc_id -> label 映射
    kc_map = {}
    sk_path = os.path.join(fp, "knowledge_skeleton.json")
    if os.path.exists(sk_path):
        with open(sk_path, encoding="utf-8") as f:
            sk = json.load(f)
        for ch in sk.get("chapters", []):
            for kc in ch.get("kcs", []):
                kc_map[kc["id"]] = kc.get("label", kc["id"])
    quiz["kcMap"] = kc_map

    body = render(quiz)
    quiz_json = json.dumps(quiz, ensure_ascii=False).replace("</", "<\\/")
    js = QUIZ_JS.replace("__QUIZ_JSON__", quiz_json)

    course = quiz.get("course") or os.path.basename(root)
    safe = re.sub(r'[\\/:*?"<>|]', "_", course)
    out = os.path.join(root, f"{safe}-复习题.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page(f"{course} · 复习题", body, extra_css=QUIZ_CSS, extra_js=js))
    print(f"复习题 -> {out}")


if __name__ == "__main__":
    main()
