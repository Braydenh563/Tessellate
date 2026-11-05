// INBOX 1557: a text input beside a button is one control height. Opens the
// Clock panel's three panes and measures every input+button sibling pair
// (getBoundingClientRect, heights equal within 1px), plus any extra surface
// named in SURFACES below. THEME=dark for the other theme.
//
//   BASE=http://127.0.0.1:8797 THEME=dark TOUCH=1 node scratchpad/ui-sweeps/inbox1557-field-button-height.js
const {boot}=require('./lib.js');
let failed=0;const check=(ok,what)=>{console.log(`${ok?'ok  ':'FAIL'} ${what}`);if(!ok)failed++;};
const pairs=()=>{
  const out=[];
  const visible=(e)=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';};
  for(const input of document.querySelectorAll('input:not(.select-native-hidden):not([type=checkbox]):not([type=radio]):not([type=range]):not([type=color]):not([type=file]):not([type=hidden]), select')){
    if(!visible(input))continue;
    const parent=input.parentElement;if(!parent)continue;
    const ir=input.getBoundingClientRect();
    for(const b of parent.querySelectorAll(':scope > button')){
      if(!visible(b))continue;
      const br=b.getBoundingClientRect();
      // Same row: the vertical ranges overlap by at least half the shorter.
      const overlap=Math.min(ir.bottom,br.bottom)-Math.max(ir.top,br.top);
      if(overlap<Math.min(ir.height,br.height)/2)continue;
      out.push({where:(parent.id?'#'+parent.id:'')+'.'+[...parent.classList].join('.'),input:(input.id?'#'+input.id:input.placeholder||input.type).slice(0,30),button:b.textContent.trim().slice(0,20)||b.getAttribute('aria-label')||'(icon)',ih:+ir.height.toFixed(1),bh:+br.height.toFixed(1)});
    }
  }
  return out;
};
(async()=>{
  const touch=!!process.env.TOUCH;
  const {browser,page}=await boot(touch?{viewport:{width:390,height:800},hasTouch:true,isMobile:true}:{viewport:{width:1440,height:900}});
  const surfaces={
    clockTimer:async()=>{await page.evaluate(()=>ensureModule('utilities').then(()=>openClockPanel('timer')));await page.waitForTimeout(700);},
    clockAlarm:async()=>{await page.evaluate(()=>openClockPanel('alarm'));await page.waitForTimeout(500);},
  };
  const all=[];
  for(const [name,open] of Object.entries(surfaces)){
    await open();
    const rows=await page.evaluate(pairs);
    for(const r of rows){all.push({name,...r});console.log(`${name}: ${r.where} [${r.input}] ${r.ih}px vs [${r.button}] ${r.bh}px`);}
  }
  // The named pairs: the timer's length field and Start, the alarm's two fields.
  await surfaces.clockTimer();
  const named=await page.evaluate(()=>{const h=(q)=>document.querySelector(q).getBoundingClientRect().height;return {field:h('.clock-length > input'),start:h('.clock-length > button')};});
  check(Math.abs(named.field-named.start)<=1,`timer: length field ${named.field.toFixed(1)}px vs Start ${named.start.toFixed(1)}px`);
  await surfaces.clockAlarm();
  const alarm=await page.evaluate(()=>{const h=(q)=>document.querySelector(q).getBoundingClientRect().height;return {time:h('.clock-alarm .select-opener'),label:h('.clock-alarm input[type=text]'),set:h('.clock-alarm button.small')};});
  check(Math.abs(alarm.time-alarm.label)<=1&&Math.abs(alarm.label-alarm.set)<=1,`alarm: time ${alarm.time.toFixed(1)} label ${alarm.label.toFixed(1)} Set alarm ${alarm.set.toFixed(1)}px`);
  const bad=all.filter(r=>Math.abs(r.ih-r.bh)>1);
  check(all.length>0,`pairs measured: ${all.length}`);
  check(bad.length===0,`pairs differing by more than 1px: ${bad.length}`);
  for(const r of bad)console.log('   differs:',JSON.stringify(r));
  await browser.close();
  console.log(failed?`${failed} FAILED`:'all ok');process.exit(failed?1:0);
})();
