# Contributing to Reuters AI Assistant Documentation 🤝

First off, thank you for considering contributing to this documentation! It's people like you that make this resource valuable for the Reuters newsroom.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Workflow](#development-workflow)
- [Style Guidelines](#style-guidelines)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)

## 📜 Code of Conduct

This project adheres to professional standards of conduct. By participating, you are expected to:

- Be respectful and inclusive
- Focus on what is best for the community
- Show empathy towards other contributors
- Accept constructive criticism gracefully

## 🎯 How Can I Contribute?

### Reporting Issues

Found a bug or inaccuracy in the documentation?

1. **Search existing issues** to avoid duplicates
2. **Create a new issue** with:
   - Clear, descriptive title
   - Detailed description of the problem
   - Steps to reproduce (if applicable)
   - Expected vs. actual behavior
   - Screenshots (if relevant)

### Suggesting Enhancements

Have an idea for improvement?

1. **Check the roadmap** in README.md
2. **Open an issue** labeled "enhancement"
3. **Describe the enhancement** with:
   - Use case/problem it solves
   - Proposed solution
   - Alternative solutions considered
   - Mockups or examples (if applicable)

### Contributing Documentation Updates

The documentation needs updates when:

- ✏️ New skills are added to Reuters AI Assistant
- 🔄 Workflows change
- 🐛 Inaccuracies are found
- ✨ UI/UX improvements are identified
- 📊 Capabilities matrix needs updates

## 🛠️ Development Workflow

### 1. Fork & Clone

```bash
# Fork the repo on GitHub first, then:
git clone https://github.com/YOUR-USERNAME/reuters-ai-assistant-skills.git
cd reuters-ai-assistant-skills
```

### 2. Create a Branch

```bash
# Use descriptive branch names
git checkout -b feature/add-new-skill-docs
git checkout -b fix/update-workflow-typo
git checkout -b docs/improve-capabilities-matrix
```

### 3. Make Your Changes

Edit `docs/index.html`:

```bash
# Open in your editor
code docs/index.html

# Or use any text editor
notepad docs/index.html  # Windows
nano docs/index.html     # Linux/Mac
```

### 4. Test Locally

```bash
# Open the file in a browser
start docs/index.html  # Windows
open docs/index.html   # macOS
xdg-open docs/index.html # Linux
```

**Check:**
- ✅ All navigation works
- ✅ No broken layouts
- ✅ Content is accurate
- ✅ Dark theme displays correctly
- ✅ Responsive on mobile (use browser dev tools)

### 5. Commit Your Changes

```bash
git add docs/index.html
git commit -m "feat: add documentation for new XYZ skill"
```

See [Commit Message Guidelines](#commit-message-guidelines) below.

### 6. Push to Your Fork

```bash
git push origin feature/add-new-skill-docs
```

### 7. Open a Pull Request

1. Go to the [original repository](https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills)
2. Click "Pull Requests" → "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template
5. Submit!

## 🎨 Style Guidelines

### HTML/CSS Guidelines

**Consistency is key!**

- Use **2-space indentation** (not tabs)
- Follow existing **naming conventions**
- Keep **inline styles** in the `<style>` section
- Use **semantic HTML** where possible
- Maintain the **dark theme color palette**:
  - Background: `#0a0a0a`
  - Cards: `#18181b`
  - Borders: `#27272a`
  - Text: `#e4e4e7`
  - Muted: `#a1a1aa`

### Content Guidelines

**Writing Style:**

- ✅ **Clear and concise** - No unnecessary jargon
- ✅ **Active voice** - "The system calls the API" not "The API is called"
- ✅ **Specific examples** - Show real workflows
- ✅ **Consistent terminology** - Use same terms throughout
- ❌ **No marketing speak** - Focus on factual information

**Documentation Principles:**

1. **Accuracy First** - Verify all technical details
2. **User-Focused** - Write for journalists using the tools
3. **Complete Workflows** - Show both user actions and backend processing
4. **Visual Hierarchy** - Use headers, lists, and formatting effectively

### Example - Good vs Bad

❌ **Bad:**
```html
<div class="card">
  <div>Important stuff about the skill</div>
</div>
```

✅ **Good:**
```html
<div class="card">
  <div class="card-title">⚡ Urgent Skill</div>
  <div class="card-content">
    <strong>Purpose:</strong> Create 1-2 sentence breaking news urgents<br>
    <strong>Model:</strong> GPT-4.1
  </div>
</div>
```

## 📝 Commit Message Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature or content
- `fix`: Bug fix or correction
- `docs`: Documentation only changes
- `style`: Formatting, missing semi-colons, etc (no code change)
- `refactor`: Code restructuring without behavior change
- `test`: Adding tests
- `chore`: Maintenance tasks

### Examples

```bash
# Adding new skill documentation
git commit -m "feat(skills): add Video Skill documentation with workflow"

# Fixing typo
git commit -m "fix(urgent): correct model name from GPT-4 to GPT-4.1"

# Improving layout
git commit -m "style(matrix): improve capabilities table responsive design"

# Updating existing content
git commit -m "docs(update): clarify archive search workflow steps"
```

### Full Example

```
feat(capabilities): add Live Market Data status to matrix

- Updated capabilities matrix with Live Market Data Call feature
- Marked as "Backlog" for Update and Blank Slate skills
- Added explanation in Archive Search section

Closes #42
```

## 🔄 Pull Request Process

### PR Title

Use the same format as commit messages:

```
feat(skills): add comprehensive Video Skill documentation
```

### PR Description Template

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Documentation update
- [ ] Style/UI improvement

## Changes Made
- Item 1
- Item 2
- Item 3

## Testing Done
- [ ] Tested locally in browser
- [ ] Checked responsive design
- [ ] Verified all links work
- [ ] Spell-checked content

## Screenshots (if applicable)
Add screenshots here

## Related Issues
Closes #issue-number
```

### Review Process

1. **Automated Checks** - GitHub Pages build must pass
2. **Code Review** - At least one approval required
3. **Testing** - Reviewer will test the changes
4. **Discussion** - Address any feedback
5. **Merge** - Once approved, PR will be merged

### After Your PR is Merged

1. **GitHub Pages Updates** - Automatic (1-2 minutes)
2. **Delete Your Branch** - Clean up your fork
3. **Sync Your Fork** - Stay up to date

```bash
# Sync with upstream
git checkout develop
git pull upstream develop
git push origin develop
```

## 🎓 Additional Resources

- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Markdown Cheatsheet](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet)
- [HTML Best Practices](https://github.com/hail2u/html-best-practices)
- [CSS Guidelines](https://cssguidelin.es/)

## 🤔 Questions?

- Open an [issue](https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills/issues)
- Start a [discussion](https://github.com/ajithkumardhevarajan/reuters-ai-assistant-skills/discussions)

## 🙏 Thank You!

Your contributions make this documentation better for everyone in the Reuters newsroom. Every improvement, no matter how small, is valued and appreciated!

---

<div align="center">
  <sub>Happy Contributing! 🎉</sub>
</div>
