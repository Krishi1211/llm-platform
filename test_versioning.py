from versioning import create_tables, save_prompt, get_prompt, list_versions, diff_versions

create_tables()

# save 3 versions of a prompt
save_prompt("summarizer", "Summarize the following text:")
save_prompt("summarizer", "Summarize the following text in 2 sentences:")
save_prompt("summarizer", "Summarize the following text in 2 sentences. Be concise and clear:")

# list all versions
print("\nAll versions:")
for v in list_versions("summarizer"):
    print(f"  v{v['version']} — {v['created_at']}")

# get latest
latest = get_prompt("summarizer")
print(f"\nLatest (v{latest['version']}):")
print(f"  {latest['content']}")

# diff v1 vs v3
print("\nDiff v1 vs v3:")
print(diff_versions("summarizer", 1, 3))