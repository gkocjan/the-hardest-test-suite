.PHONY: demo regression clean

demo:  ## run the suite against the good model (green)
	uv run pytest tests -v --html=reports/report.html --self-contained-html

regression:  ## same tests, broken model 2.2-rc (red — this is the point)
	MODEL_VERSION=2.2-rc uv run pytest tests -v \
		--html=reports/regression-report.html --self-contained-html; \
	echo "exit $$? — a red report is the expected outcome here"

clean:
	rm -rf reports .runtime .pytest_cache
