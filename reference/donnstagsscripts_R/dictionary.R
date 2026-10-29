library(word2vec)

# create
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

char_ad <- tokens_ad |>
  as.list() |>
  stringi::stri_join_list(sep = " ")

# set.seed(1234)
#
# word2vec_model <- word2vec(
#   x = char_ad,
#   type = "cbow",
#   dim = 300, # 50 is faster, 300 is better
#   window = 10,
#   threads = parallel::detectCores() - 2
# )
#
# write.word2vec(
#   word2vec_model,
#   file = paste0("word2vec-model-", format(Sys.time(), "%Y-%m-%d-%H-%M-%S"), ".bin")
# )

word2vec_model <- read.word2vec("word2vec-model-2026-08-17-16-18-11.bin")

print(predict(word2vec_model,
              newdata = c("apfel"),
              type = "nearest",
              top_n = 50
))


############################# checking terms

dfm_ad <- tokens_ad |> dfm()

terms_to_check <- c("^holz$")

# Select the columns corresponding to the terms
selected_dfm <- dfm_select(
  dfm_ad,
  pattern = terms_to_check,
  selection = "keep",
  valuetype = "regex"
)

# Sum the counts for each term
term_frequencies <- sort(colSums(selected_dfm), decreasing = TRUE)

# Print the frequencies
print(term_frequencies)


kwic(
  tokens_ad,
  pattern = "holzgerechtigkeit",
  window = 5,
  valuetype = c("glob", "regex", "fixed"),
  case_insensitive = TRUE
)


# Create numeric year and month docvars

corpus_verkauf <- corpus_subset(corpus_ad, category == "verkauf")

docvars(corpus_verkauf, "year") <- as.integer(
  format(docvars(corpus_verkauf, "date"), "%Y")
)
df_corpus <- data.frame(corpus_verkauf)
df_corpus$date <- docvars(corpus_verkauf, "date")
df_corpus$year <- docvars(corpus_verkauf, "year")

textiles_year <- df_corpus |>
  as.data.frame() |>
  mutate(
    linen  = str_detect(corpus_verkauf, regex("\\bleinwand|\\bleine", ignore_case = TRUE)),
    cotton = str_detect(corpus_verkauf, regex("\\bbaumw", ignore_case = TRUE)),
    silk   = str_detect(corpus_verkauf, regex("\\bseide", ignore_case = TRUE))
  ) |>
  summarise(
    linen = sum(linen),
    cotton = sum(cotton),
    silk = sum(silk),
    .by = year
  ) |>
  pivot_longer(
    cols = c(linen, cotton, silk),
    names_to = "material",
    values_to = "n"
  ) |>
  group_by(year) |>
  mutate(
    total = sum(n),
    share = n / total
  ) |>
  ungroup()


textiles_5year <- textiles_year |>
  mutate(period = floor(year / 5) * 5) |>
  group_by(period, material) |>
  summarise(
    n = sum(n),
    .groups = "drop"
  ) |>
  group_by(period) |>
  mutate(
    total = sum(n),
    share = n / total
  ) |>
  ungroup()


ggplot(
  textiles_5year,
  aes(x = period, y = share, fill = material)
) +
  geom_area(
    position = "stack",
    alpha = 0.85
  ) +
  scale_y_continuous(
    labels = scales::percent,
    expand = c(0, 0)
  ) +
  scale_x_continuous(
    breaks = seq(1730, 1840, 10),
    expand = expansion(mult = c(0.01, 0.01))
  ) +
  scale_fill_manual(
    values = c(
      "cotton" = "#D55E00",
      "linen"  = "#009E73",
      "silk"   = "#0072B2"
    ),
    labels = c(
      "cotton" = "Baumwolle",
      "linen"  = "Leinen",
      "silk"   = "Seide"
    )
  ) +
  labs(
    title = "Zusammensetzung der Textilien in Verkaufsanzeigen",
    subtitle = "Anteile von Leinen, Baumwolle und Seide, Fünfjahresperioden",
    x = NULL,
    y = NULL,
    fill = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_blank(),
    legend.position = "top",
    plot.title = element_text(face = "bold")
  )




# ------------------------------------------------------------
# 1. All Verkauf advertisements
# ------------------------------------------------------------

corpus_verkauf <- corpus_subset(corpus_ad, category == "verkauf")

df_verkauf <- data.frame(
  doc_id = docnames(corpus_verkauf),
  text   = as.character(corpus_verkauf),
  date   = docvars(corpus_verkauf, "date")
) |>
  mutate(
    year = as.integer(format(date, "%Y"))
  )

# ------------------------------------------------------------
# 2. Apply current dictionary
#    IMPORTANT: these predictions are NOT used for sampling
# ------------------------------------------------------------

df_verkauf <- df_verkauf |>
  mutate(
    pred_linen = str_detect(
      text,
      regex("\\bleinwand|\\bleine", ignore_case = TRUE)
    ),

    pred_cotton = str_detect(
      text,
      regex("\\bbaumw", ignore_case = TRUE)
    ),

    pred_silk = str_detect(
      text,
      regex("\\bseide", ignore_case = TRUE)
    )
  )

# ------------------------------------------------------------
# 3. Divide the whole period into four validation strata
# ------------------------------------------------------------

df_verkauf <- df_verkauf |>
  mutate(
    period = case_when(
      year >= 1730 & year <= 1759 ~ "1730-1759",
      year >= 1760 & year <= 1789 ~ "1760-1789",
      year >= 1790 & year <= 1819 ~ "1790-1819",
      year >= 1820 & year <= 1842 ~ "1820-1842",
      TRUE ~ NA_character_
    )
  )

# ------------------------------------------------------------
# 4. Random sample: 250 ads per period = 1000 total
#    Sampling is from ALL Verkauf ads
# ------------------------------------------------------------

validation_1000 <- df_verkauf |>
  filter(!is.na(period)) |>
  group_by(period) |>
  slice_sample(n = 250) |>
  ungroup() |>
  arrange(year, date)

# ------------------------------------------------------------
# 5. Add empty columns for manual validation
# ------------------------------------------------------------

validation_1000 <- validation_1000 |>
  mutate(
    gold_linen  = NA,
    gold_cotton = NA,
    gold_silk   = NA
  )

# Check sample
validation_1000 |>
  count(period)

# How many dictionary-positive cases happened to occur?
validation_1000 |>
  summarise(
    linen_matches  = sum(pred_linen),
    cotton_matches = sum(pred_cotton),
    silk_matches   = sum(pred_silk)
  )

# ------------------------------------------------------------
# 6. Export for manual coding, if desired
# ------------------------------------------------------------

write.csv(
  validation_1000,
  "validation_textiles_1000.csv",
  row.names = FALSE,
  fileEncoding = "UTF-8"
)
