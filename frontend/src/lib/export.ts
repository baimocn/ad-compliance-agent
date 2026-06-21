interface BatchResultItem {
  index: number
  text: string
  status: string
  overall_risk: string
  violation_count: number
  violations: { text: string; category: string; severity: string; suggestion: string }[]
  error?: string
}

export function exportBatchResultsToCsv(results: BatchResultItem[], filename = "审查报告.csv") {
  const rows = [["序号", "文案", "状态", "风险等级", "违规数", "违规详情", "替代建议", "错误信息"]]

  for (const r of results) {
    const violationDetails = (r.violations || [])
      .map((v) => `[${v.category}]${v.text}`)
      .join("; ")
    const suggestions = (r.violations || [])
      .map((v) => v.suggestion)
      .filter(Boolean)
      .join("; ")

    rows.push([
      String(r.index),
      r.text,
      r.status === "safe" ? "安全" : r.status === "violation_found" ? "有违规" : r.status,
      r.overall_risk,
      String(r.violation_count),
      violationDetails,
      suggestions,
      r.error || "",
    ])
  }

  const csv = rows
    .map((row) =>
      row
        .map((cell) => {
          const escaped = cell.replace(/"/g, '""')
          return /[",\n]/.test(escaped) ? `"${escaped}"` : escaped
        })
        .join(",")
    )
    .join("\n")

  const BOM = "\uFEFF"
  const blob = new Blob([BOM + csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
