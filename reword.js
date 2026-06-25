// 替换所有 pick 为 reword 的简单脚本
const fs = require('fs');
const path = process.argv[2];
const content = fs.readFileSync(path, 'utf8');
const lines = content.split('\n');
const newLines = lines.map(line => {
    if (line.startsWith('pick ')) {
        return 'reword ' + line.substring(5);
    }
    return line;
});
fs.writeFileSync(path, newLines.join('\n'), 'utf8');
