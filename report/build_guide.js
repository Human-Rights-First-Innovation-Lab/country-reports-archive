const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, LevelFormat, convertInchesToTwip,
} = require(path.join(__dirname, 'node_modules', 'docx'));

const INK='12171D', MUTED='5B6673', RULE='DDE3EA';
const BLUE='1163A0', RED='A32C25', BAND='F4F6F8', AMBER='7A4A06';
const SERIF='Georgia', SANS='Arial', MONO='Consolas';

const PAGE = { size:{width:12240,height:15840},
               margin:{top:1440,bottom:1440,left:1440,right:1440} };
const CW = 12240 - 2880;
const NONE = {style:BorderStyle.NONE,size:0,color:'FFFFFF'};
const noB = {top:NONE,bottom:NONE,left:NONE,right:NONE,insideHorizontal:NONE,insideVertical:NONE};

const h1 = t => new Paragraph({ heading:HeadingLevel.HEADING_1, spacing:{before:400,after:150},
  children:[new TextRun({text:t,font:SERIF,size:30,bold:true,color:INK})] });
const h2 = t => new Paragraph({ heading:HeadingLevel.HEADING_2, spacing:{before:260,after:100},
  children:[new TextRun({text:t,font:SANS,size:22,bold:true,color:INK})] });
const p = (runs,o={}) => new Paragraph({ spacing:{after:o.after??170,line:288},
  indent:o.indent, children:(Array.isArray(runs)?runs:[runs]).map(r =>
    typeof r==='string' ? new TextRun({text:r,font:SANS,size:21,color:INK})
                        : new TextRun({font:SANS,size:21,color:INK,...r})) });
const code = lines => new Paragraph({
  spacing:{before:80,after:160}, shading:{type:ShadingType.CLEAR,fill:BAND,color:'auto'},
  indent:{left:convertInchesToTwip(0.12),right:convertInchesToTwip(0.12)},
  border:{left:{style:BorderStyle.SINGLE,size:12,color:BLUE}},
  children: lines.flatMap((l,i)=>[
    ...(i? [new TextRun({break:1})] : []),
    new TextRun({text:l,font:MONO,size:18,color:INK})]) });
const bullet = runs => new Paragraph({ numbering:{reference:'b',level:0}, spacing:{after:90},
  children:(Array.isArray(runs)?runs:[runs]).map(r =>
    typeof r==='string'?new TextRun({text:r,font:SANS,size:20,color:INK})
                       :new TextRun({font:SANS,size:20,color:INK,...r})) });
const step = (n,ref='s1') => new Paragraph({ numbering:{reference:ref,level:0}, spacing:{after:110},
  children:(Array.isArray(n)?n:[n]).map(r =>
    typeof r==='string'?new TextRun({text:r,font:SANS,size:21,color:INK})
                       :new TextRun({font:SANS,size:21,color:INK,...r})) });
const step2=(n)=>step(n,'s2');
const step3=(n)=>step(n,'s3');
const link = text => ({text, font:SANS, size:21, color:BLUE, bold:true});

const callout = (title,paras,accent) => new Table({
  columnWidths:[CW], width:{size:CW,type:WidthType.DXA}, borders:noB,
  rows:[new TableRow({children:[new TableCell({
    width:{size:CW,type:WidthType.DXA},
    shading:{type:ShadingType.CLEAR,fill:BAND,color:'auto'},
    margins:{top:200,bottom:200,left:220,right:200},
    borders:{...noB,left:{style:BorderStyle.SINGLE,size:18,color:accent}},
    children:[
      new Paragraph({spacing:{after:110},children:[new TextRun({
        text:title.toUpperCase(),font:SANS,size:15,bold:true,color:accent,characterSpacing:40})]}),
      ...paras.map((r,i)=>new Paragraph({spacing:{after:i===paras.length-1?0:120,line:276},
        children:(Array.isArray(r)?r:[r]).map(x =>
          typeof x==='string'?new TextRun({text:x,font:SANS,size:20,color:INK})
                             :new TextRun({font:SANS,size:20,color:INK,...x}))})),
    ]})]})]});

/* ---- routes table ---- */
const C=[Math.floor(CW*0.30),Math.floor(CW*0.42),Math.floor(CW*0.28)];
const tc=(txt,i,o={})=>new TableCell({ width:{size:C[i],type:WidthType.DXA},
  margins:{top:110,bottom:110,left:130,right:130},
  borders:{...noB,bottom:{style:BorderStyle.SINGLE,size:4,color:RULE}},
  shading:o.head?{type:ShadingType.CLEAR,fill:BAND,color:'auto'}:undefined,
  children:[new Paragraph({children:[new TextRun({text:txt,font:SANS,size:19,
    bold:!!(o.head||o.b),color:o.head?MUTED:INK})]})]});

const doc = new Document({
  creator:'Human Rights First', title:'Asking questions about the Country Reports',
  numbering:{config:[
    {reference:'b',levels:[{level:0,format:LevelFormat.BULLET,text:'•',
      alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:convertInchesToTwip(0.30),
      hanging:convertInchesToTwip(0.18)}}}}]},
    ...['s1','s2','s3'].map(r=>({reference:r,levels:[{level:0,format:LevelFormat.DECIMAL,
      text:'%1.',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{
      left:convertInchesToTwip(0.34),hanging:convertInchesToTwip(0.22)}}}}]})),
  ]},
  sections:[{ properties:{page:PAGE},
    headers:{default:new Header({children:[new Paragraph({spacing:{after:0},
      border:{bottom:{style:BorderStyle.SINGLE,size:4,color:RULE}},
      children:[new TextRun({text:'Human Rights First  ·  Country Reports archive',
        font:SANS,size:15,color:MUTED})]})]})},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,
      children:[new TextRun({children:['Page ',PageNumber.CURRENT,' of ',PageNumber.TOTAL_PAGES],
        font:SANS,size:15,color:MUTED})]})]})},
    children:[
      new Paragraph({spacing:{before:200,after:110},children:[new TextRun({
        text:'GETTING STARTED',font:SANS,size:16,bold:true,color:MUTED,characterSpacing:50})]}),
      new Paragraph({spacing:{after:150},children:[new TextRun({
        text:'Asking questions about the Country Reports',font:SERIF,size:42,bold:true,color:INK})]}),
      new Paragraph({spacing:{after:320,line:300},children:[new TextRun({
        text:'We keep a complete archive of the State Department’s Country Reports on Human Rights Practices — 389 reports across the 2023 and 2024 editions. You can ask Claude questions about any of them. This takes about ten minutes to set up and costs nothing beyond your existing Claude account.',
        font:SERIF,size:23,color:'39424D'})]}),

      h1('Pick a way in'),
      p('Three options. They all reach the same archive — the difference is how much you install.'),
      new Table({columnWidths:C,width:{size:CW,type:WidthType.DXA},borders:noB,rows:[
        new TableRow({tableHeader:true,children:[tc('Option',0,{head:true}),tc('Best for',1,{head:true}),tc('To install',2,{head:true})]}),
        new TableRow({children:[tc('Claude on the web',0,{b:true}),tc('Most people. Nothing to set up.',1),tc('Nothing',2)]}),
        new TableRow({children:[tc('Claude desktop app',0,{b:true}),tc('If you already use it for other work',1),tc('The app',2)]}),
        new TableRow({children:[tc('Terminal',0,{b:true}),tc('If you are comfortable on a command line',1),tc('Git, Claude Code',2)]}),
      ]}),
      new Paragraph({spacing:{after:200},children:[new TextRun('')]}),
      p([{text:'If you are not sure, use the web option. ',bold:true},
         {text:'It needs no installation and does everything the others do for asking questions.'}]),

      h1('Option 1 — Claude on the web'),
      step([{text:'Go to '},link('claude.ai/code'),
            {text:' and sign in with your Human Rights First account.'}]),
      step('Connect the archive repository when prompted for a repository to work in:'),
      code(['Human-Rights-First-Innovation-Lab/country-reports-archive']),
      step('Ask your first question (see below). That is the whole setup.'),
      p([{text:'The exact wording of the buttons may differ slightly from this guide as the interface changes — you are looking for the option to open or connect a GitHub repository.',italics:true,color:MUTED,size:19}]),

      h1('Option 2 — Claude desktop app'),
      step2('Open the Claude app and start a session in the Code tab.'),
      step2([{text:'Choose the folder containing the archive. If you do not have it yet, download it from '},
            link('github.com/Human-Rights-First-Innovation-Lab/country-reports-archive'),
            {text:' — use the green Code button, then Download ZIP, and unzip it somewhere you will remember.'}]),
      step2('Ask your first question.'),

      h1('Option 3 — Terminal'),
      step3('Clone the archive. It is public, so you do not need any credentials:'),
      code(['git clone https://github.com/Human-Rights-First-Innovation-Lab/\\',
            '  country-reports-archive.git',
            'cd country-reports-archive']),
      step3('Start Claude Code in that folder:'),
      code(['claude']),
      p([{text:'Optional. ',bold:true},
         {text:'Only needed if you want to run the analysis scripts yourself rather than asking Claude to:'}]),
      code(['python3 -m venv .venv','.venv/bin/pip install -r requirements.txt']),

      h1('Your first question'),
      p('Whichever route you took, start by asking:'),
      code(['What can I do with this repo?']),
      p('The archive carries its own instructions, so Claude will orient itself and tell you what is available before you ask anything substantive.'),

      h2('Questions that work well'),
      bullet('What does the 2024 Kenya report say about press freedom?'),
      bullet('Summarise what changed for Hungary between the 2023 and 2024 editions.'),
      bullet('Which organisations does the 2024 Sudan report attribute information to?'),
      bullet('Find every mention of enforced disappearance in East African reports.'),
      bullet('How many countries cite Human Rights Watch in the 2024 edition?'),
      bullet('Show me every quantitative claim about child labour in the 2024 reports.'),

      h2('Questions to be careful with'),
      p('Anything comparing the two editions section by section. The 2024 edition reorganised the reports completely, so the sections do not line up. Claude should tell you this; ask for a country-level or topic-level comparison instead.'),

      h1('Five things to know about this data'),
      p('These are not footnotes. Each one will produce a confident wrong answer if you do not know it.'),

      callout('1 — A missing topic usually means cut reporting, not improvement',
        [[{text:'The 2024 reports are about two-thirds shorter than the 2023 ones. Median length fell from roughly 53,000 characters to 18,000, and '},
          {text:'not one of the 192 countries covered in both editions got longer.',bold:true},
          {text:' So when a 2024 report is silent on something the 2023 report covered, the likeliest explanation is that the reporting was cut — not that the situation improved. Absence of reporting is not evidence of absence of abuse.'}]], RED),
      new Paragraph({spacing:{after:170},children:[new TextRun('')]}),

      callout('2 — The reports have no footnotes',
        ['These reports carry no bibliography. Sources appear only inside sentences — “according to UNICEF”, “the KNCHR reported 82 cases”. Our extracted source lists were built by pattern-matching those sentences, so they are a research index rather than a record of what the State Department formally cited. Always read the sentence before quoting a source.'], AMBER),
      new Paragraph({spacing:{after:170},children:[new TextRun('')]}),

      callout('3 — The two editions cannot be compared section by section',
        ['The 2023 edition used seven thematic sections; 2024 uses three. Only two headings survive in recognisable form. A section-by-section comparison produces numbers that look precise and mean nothing. Country-level and source-level comparisons are fine.'], AMBER),
      new Paragraph({spacing:{after:170},children:[new TextRun('')]}),

      callout('4 — North Macedonia’s 2024 report is missing',
        ['The report exists, but the State Department’s website blocks automated downloads of that one file. It is excluded from every figure rather than estimated. Do not read its absence as a finding.'], AMBER),
      new Paragraph({spacing:{after:170},children:[new TextRun('')]}),

      callout('5 — Ask for counts to be computed, not read',
        [[{text:'Claude will miscount if it tries to tally something by reading 389 documents, and the error will not be visible to you. The archive includes extracted tables for exactly this. If you want a number, ask for it explicitly: '},
          {text:'“Compute that from the CSVs rather than by reading the reports.”',bold:true}]], RED),

      h1('If you are publishing anything'),
      p([{text:'Every report in the archive is stored with the web address it came from and a checksum, in '},
         {text:'data/<year>/manifest.json',font:MONO,size:19},
         {text:'. That file is the provenance record. Ask Claude for the source PDF link for any report you quote — the original documents are in the archive too, exactly as published.'}]),
      p([{text:'Before citing extracted figures, read '},
         {text:'corpus/METHODOLOGY.md',font:MONO,size:19},
         {text:' in the archive. It sets out what the numbers can and cannot support.'}]),
      p('These reports are works of the US Government and are in the public domain, so there is no restriction on quoting or republishing them.'),

      h1('Getting help'),
      p([{text:'The archive is at '},
         link('github.com/Human-Rights-First-Innovation-Lab/country-reports-archive'),
         {text:'. If something is not working, or you want a question answered that the archive cannot handle, raise an issue there or ask Jason.'}]),
      p([{text:'The 2025 edition has not been released yet. When it is, it will be added to the same archive and your setup will not change.',italics:true,color:MUTED,size:20}]),
    ]}],
});

Packer.toBuffer(doc).then(b=>{
  const out = path.join(__dirname,'Getting-Started-Country-Reports.docx');
  fs.writeFileSync(out,b); console.log('wrote',out,b.length,'bytes');
});
