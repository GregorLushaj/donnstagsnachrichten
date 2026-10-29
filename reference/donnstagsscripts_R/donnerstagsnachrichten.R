library(tidyverse)
library(quanteda)
library(stringi)
library(quanteda.textstats)
library(patchwork)

# ---------------------------------------------------------------------------
# load_dn(): read the issues and merge them into one document per ad
# ---------------------------------------------------------------------------
# Only the CSV READ is cached, not the merge. Reading the ~8,000 files takes
# minutes; the merge and de-hyphenation take about a minute. Caching only the
# read means edits to the merging or de-hyphenation logic take effect
# immediately, with no stale-cache risk.
#
#   rebuild = TRUE  forces a fresh read, e.g. after new issues are added to
#                   the folder (file.exists() cannot tell that it changed)
#
# Returns zwb_merged: one row per advertisement.

load_dn <- function(dir     = "donnerstagsnachrichten",
                    cache   = "dn_merged.rds",
                    rebuild = FALSE) {

  # cache hit: return the finished object and skip everything below
  if (!rebuild && file.exists(cache)) {
    zwb_merged <- read_rds(cache)
    message("loaded merged corpus from ", cache,
            " (", nrow(zwb_merged), " documents)")
    return(zwb_merged)
  }

  files <- list.files(dir, pattern = "^(ZWB|DN).*\\.csv$", full.names = TRUE)
  message("reading ", length(files), " files...")

  zwb <- map_dfr(files, function(file) {
    stem <- tools::file_path_sans_ext(basename(file))

    read_csv(file, show_col_types = FALSE) %>%
      mutate(
        issue = stem,
        row_in_issue = row_number(),
        date = as.Date(str_remove(date, "^(ZWB|DN)"), format = "%Y%m%d")
      )
  })

  zwb_merged <- zwb %>%
    group_by(issue) %>%
    mutate(document_no = cumsum(continuation != 1)) %>%
    ungroup() %>%
    arrange(issue, row_in_issue) %>%
    group_by(issue, document_no) %>%
    summarise(
      text_lines = paste(text, collapse = "\n"),
      type       = first(type),
      category   = first(category),
      date       = first(date),
      page_start = first(page),
      page_end   = last(page),
      .groups = "drop"
    ) %>%
    mutate(
      doc_id = paste0(issue, "_", sprintf("%03d", document_no)),
      text = stri_replace_all_regex(
        text_lines,
        "(\\p{L})[-\u2010\u2011\u00AC\u2E17=][ \\t]*\\n[ \\t]*(?!(?:und|oder|sowie|bzw|beziehungsweise)\\b)(\\p{L})",
        "$1$2"
      ),
      text = stri_replace_all_regex(text, "\\s*\\n\\s*", " "),
      text = stri_trim_both(text),
      year = year(date)
    )

  write_rds(zwb_merged, cache, compress = "gz")
  message("cached ", nrow(zwb_merged), " documents to ", cache)

  zwb_merged
}

zwb_merged <- load_dn()

CLS <- "labor_classification/verschiedenes_pre1833_luna_audited.csv"

cls <- read_csv(CLS, show_col_types = FALSE,
                col_select = c(doc_id, year, final_category, labour_subtype))

cat("classification rows:", nrow(cls),
    "| matched to corpus:", sum(cls$doc_id %in% zwb_merged$doc_id), "\n")

zwb_merged <- zwb_merged %>%
  left_join(cls %>% select(doc_id, final_category, labour_subtype),
            by = "doc_id") |>
  mutate(
    category_update = case_when(
      year <= 1832 & !is.na(final_category) ~ final_category,
      year <= 1832                          ~ category,
      TRUE                                  ~ category
    )
  )

ads <- zwb_merged %>% filter(type == "ad")

corpus_ad <- corpus(ads, text_field = "text", docid_field = "doc_id")

table(corpus_ad$category_update, useNA = "ifany")

# corpus_sale <- corpus_ad |> corpus_subset(category == "verkauf")

tokens_ad <- corpus_ad |>
  tokens(
    remove_punct = TRUE,
    remove_symbols = TRUE,
    remove_numbers = TRUE,
    remove_url = TRUE,
    remove_separators = TRUE,
    split_hyphens = TRUE,
    split_tags = TRUE,
    verbose = TRUE
  ) |>
  tokens_tolower()


# Let's create a document feature matrix
dfm_ad <- tokens_ad |> dfm()

# We can take a look at the most frequent terms
dfm_ad |> topfeatures()


# Create numeric year and month docvars
docvars(dfm_ad, "year") <- as.integer(
  format(docvars(dfm_ad, "date"), "%Y")
)

docvars(dfm_ad, "month") <- as.integer(
  format(docvars(dfm_ad, "date"), "%m")
)

table(dfm_ad$year)

# ads over time
docvars(dfm_ad) |>
  ggplot(aes(x = year)) +
  geom_bar()


# Build a yearly count table for all categories
ad_counts <- docvars(dfm_ad) |>
  count(year, category_update)

# Plot: counts over time
ad_counts |>
  ggplot(aes(x = year, y = n)) +
  geom_line() +
  geom_point() +
  labs(
    title = "Number of ads over time",
    x = NULL, y = "Number of ads"
  ) + facet_wrap(~ category_update) +
  scale_y_log10()
