// 修改 git commit message 的脚本
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// 设置环境变量
process.env.GIT_SEQUENCE_EDITOR = 'node -e "'
    + 'const fs=require(\"fs\");'
    + 'const txt=fs.readFileSync(process.argv[2],\"utf8\");'
    + 'const lines=txt.split(String.fromCharCode(10));'
    + 'for(let i=0;i<lines.length;i++){'
    + 'if(lines[i].startsWith(\"pick \"))'
    + 'lines[i]=\"reword \"+lines[i].substring(5);'
    + '}'
    + 'fs.writeFileSync(process.argv[2],lines.join(String.fromCharCode(10)));'
    + '"';

console.log('Environment variable set');
console.log('GIT_SEQUENCE_EDITOR:', process.env.GIT_SEQUENCE_EDITOR);
