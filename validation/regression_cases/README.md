# regression_cases/ — 新 failure cases 放這裡

- 永久凍結 `acceptance_set_v1`，不要改它。
- 未來發現的新失敗模式（新轉播版式、新 graphic 包、特殊球場），在此新增獨立 case 目錄。
- 每個 case 包含：短 clip + `labels.jsonl` (同 acceptance schema) + `README.md` 說明失敗原因。

```
regression_cases/
  README.md
  <case-id>/
    README.md
    clip.mp4 (optional, git-lfs 或外部連結)
    labels.jsonl
```
