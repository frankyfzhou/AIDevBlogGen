---
description: "Generate a weekly AI Dev blog post on demand. Use when: generate blog post, create weekly post, write AI news article, run the blog pipeline."
agent: "agent"
---

Generate this week's AI Dev Weekly blog post by running the full pipeline:

1. First, confirm the environment is set up:
   - Check that `OPENAI_API_KEY` is set (in `.env` or environment)
   - Check that Python dependencies are installed (`pip install -r requirements.txt`)

2. Run the pipeline:
   ```bash
   python -m src.main --no-push --verbose
   ```

3. After generation, show me:
   - The title of the generated post
   - The file path where it was saved
   - A brief summary of the stories covered

4. Ask if I want to:
   - Preview it locally (`cd blog && hugo server -D`)
   - Commit and push it (`git add blog/content/posts/ && git commit -m "blog: add weekly post" && git push`)
   - Regenerate with different parameters
