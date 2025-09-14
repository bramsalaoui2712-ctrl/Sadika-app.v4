const { execSync } = require('child_process');
const fs = require('fs');
try {
  fs.mkdirSync('www', { recursive: true });
  if (fs.existsSync('frontend/public')) {
    execSync('cp -R frontend/public/* www/', { stdio: 'inherit' });
  } else if (fs.existsSync('frontend/dist')) {
    execSync('cp -R frontend/dist/* www/', { stdio: 'inherit' });
  } else if (fs.existsSync('frontend/build')) {
    execSync('cp -R frontend/build/* www/', { stdio: 'inherit' });
  } else {
    fs.writeFileSync('www/index.html', '<h1>Sadika placeholder</h1>');
  }
  console.log('✅ Web copié vers www/');
} catch (e) {
  console.error('❌ Échec copie web → www/', e);
  process.exit(0); // ne bloque pas le pipeline
}
