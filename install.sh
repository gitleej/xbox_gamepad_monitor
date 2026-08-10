#!/usr/bin/env bash
# 安装 Xbox Gamepad Monitor 到当前用户的应用菜单
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/xbox_gamepad_monitor"
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/xbox_gamepad_monitor.desktop" <<DESKTOP_EOF
[Desktop Entry]
Type=Application
Name=Xbox Gamepad Monitor
Comment=Xbox 手柄实时状态可视化
Exec=$DIR/xbox_gamepad_monitor
Icon=$DIR/icon.png
Terminal=false
Categories=Utility;
StartupNotify=true
DESKTOP_EOF
echo "安装完成：应用菜单中可搜索 Xbox Gamepad Monitor"
