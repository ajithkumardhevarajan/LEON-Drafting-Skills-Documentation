# Reuters AI Assistant - Skills & Capabilities Reference 🚀

> Interactive documentation for Reuters AI Assistant skills, workflows, and capabilities

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub Pages](https://img.shields.io/badge/docs-live-brightgreen)](https://ajithkumardhevarajan.github.io/reuters-ai-assistant-skills/)
[![Made with Love](https://img.shields.io/badge/Made%20with-❤️-red.svg)](https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills)

## 📖 Overview

A comprehensive, interactive reference guide documenting all Reuters AI Assistant skills, including detailed workflows, capabilities matrices, and AI model usage. This documentation provides transparency into how each skill processes requests, from user input through backend orchestration to final output.

**🌐 [View Live Documentation](https://ajithkumardhevarajan.github.io/reuters-ai-assistant-skills/)**

## ✨ Features

- **🎯 Comprehensive Skill Documentation**
  - Generic AI Assistant (Orchestration Layer)
  - Urgent Skill (Breaking News)
  - Update Skill (Story Updates)
  - Blank Slate Skill (Original Story Creation)
  - Archive Search Integration

- **🔄 Complete Workflows**
  - User interaction flows
  - Backend processing details
  - AI model execution steps
  - Prompt usage explanations

- **📊 Capabilities Matrix**
  - Feature comparison across all skills
  - AI Assistant vs LEON integration capabilities
  - Feature availability status (Available/In Progress/Backlog)

- **🤖 AI Model Details**
  - Gemini 2.5 Flash - Fast Q&A and content analysis
  - GPT-4.1 - Structured news writing
  - Gemini 2.5 Pro - Deep synthesis and multi-source stories

- **🎨 Modern Dark UI**
  - State-of-the-art minimalist design
  - Optimized for readability
  - Responsive layout
  - No unnecessary scrolling

## 🚀 Quick Start

### View Online
Simply visit the [live documentation](https://ajithkumardhevarajan.github.io/reuters-ai-assistant-skills/)

### Run Locally
```bash
# Clone the repository
git clone https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills.git

# Navigate to docs
cd reuters-ai-assistant-skills/docs

# Open in browser
open index.html  # macOS
start index.html # Windows
xdg-open index.html # Linux
```

## 📂 Repository Structure

```
reuters-ai-assistant-skills/
├── docs/                          # GitHub Pages documentation
│   ├── index.html                # Main interactive documentation
│   └── README.md                 # Documentation guide
├── README.md                     # This file
├── CONTRIBUTING.md               # Contribution guidelines
└── LICENSE                       # MIT License
```

## 🎯 Skills Covered

### 1. Generic AI Assistant 🤖
The orchestration layer that intelligently routes all user requests.

**Key Features:**
- Intent interpretation
- Intelligent routing to appropriate skills
- Tool selection (archive search, document access)
- Context management
- Conversation state tracking

**Model:** Gemini 2.5 Flash

### 2. Urgent Skill ⚡
Create 1-2 sentence breaking news urgents from news flashes.

**Key Features:**
- Processes news alerts in order of importance
- Generates Reuters-style urgents (max 80 words, 2 sentences)
- Automatic headline generation
- Refinement capabilities

**Model:** GPT-4.1

### 3. Update Skill 🔄
Update existing Reuters stories with new information.

**Key Features:**
- Automatic archive search based on original story + new input
- Two modes: Add Background or Rewrite
- Generates 25-word advisory explaining changes
- Source references per paragraph

**Model:** Gemini 2.5 Pro

### 4. Blank Slate Skill ✨
Create complete 500-word stories from research and sources.

**Key Features:**
- Synthesizes multiple archive sources
- Structured story format (Lead, Details, Nut Graph, Quotes, Background)
- Automatic headline and bullet point generation
- Source categorization (New Content vs Background)

**Model:** Gemini 2.5 Pro

### 5. Archive Search 🔍
Semantic search integration across Reuters Text Archive.

**Key Features:**
- Context-aware query generation
- Relevance ranking
- Multi-query search
- Source categorization for different skills

## 🛠️ Technologies

- **Frontend:** Pure HTML5, CSS3, JavaScript
- **Design:** Dark minimalist UI with modern aesthetics
- **Hosting:** GitHub Pages
- **Version Control:** Git & GitHub

## 📊 Capabilities Matrix Highlights

| Capability | Urgent | Update | Blank Slate |
|-----------|--------|---------|-------------|
| User Intent Input | ✓ | ✓ | ✓ |
| Source Citation | ✓ | ✓ | ✓ |
| Alert Selection | ✓ | — | — |
| Archive Story Selection | — | ✓ | ✓ |
| Auto Coding | Backlog | Backlog | Backlog |
| Auto Slugging | Backlog | Backlog | Backlog |
| Style Guide Compliance | ✓ | ✓ | ✓ |

*Full matrix available in [live documentation](https://ajithkumardhevarajan.github.io/reuters-ai-assistant-skills/)*

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting PRs.

### Quick Contribution Steps

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes to `docs/index.html`
4. Test locally by opening the file in a browser
5. Commit using conventional commits (`git commit -m 'feat: add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Ajithkumar Dhevarajan**
- GitHub: [@ajithkumardhevarajan](https://github.com/ajithkumardhevarajan)

## 🙏 Acknowledgments

- Reuters AI Assistant Team
- Thomson Reuters for the AI infrastructure
- All contributors and reviewers

## 📮 Contact & Support

- **Issues:** [GitHub Issues](https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills/issues)
- **Discussions:** [GitHub Discussions](https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills/discussions)

## 🗺️ Roadmap

- [x] Initial documentation release
- [x] Interactive capabilities matrix
- [x] Complete workflow documentation
- [ ] Video walkthroughs
- [ ] API integration examples
- [ ] Multi-language support
- [ ] Dark/Light theme toggle

---

<div align="center">
  <sub>Built with ❤️ for the Reuters newsroom</sub>
  <br>
  <sub>© 2026 Ajithkumar Dhevarajan. All rights reserved.</sub>
</div>
