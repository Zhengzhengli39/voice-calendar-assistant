# 语音驱动日程助手 - Google Calendar自动化

## 项目简介

这是一个语音驱动的日程助手Web应用，允许用户通过语音对话在Google日历中创建日程安排。项目采用浏览器自动化技术（Playwright）操作Google日历，无需使用Google Calendar API。

## 功能特点

1. **语音交互**：通过语音对话添加日程
2. **自然语言理解**：解析中文日期时间（如"明天上午十点到十一点"）
3. **浏览器自动化**：使用Playwright自动操作Google Calendar
4. **登录状态保持**：保存并复用Google登录状态
5. **日程冲突检测**：自动检查并提示时间冲突
6. **Web界面**：简洁美观的用户界面

## 技术栈

- **后端**：Python Flask
- **前端**：HTML5, CSS3, JavaScript (原生)
- **语音处理**：SpeechRecognition, pyttsx3
- **浏览器自动化**：Playwright
- **自然语言处理**：jieba, dateparser

## 环境要求

- Python 3.8+
- Chrome/Firefox浏览器
- 麦克风（用于语音输入）
- 扬声器（用于语音输出）

## 安装步骤

### 1. 克隆项目
```bash
git clone <repository-url>
cd voice-calendar-assistant