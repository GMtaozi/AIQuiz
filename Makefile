.PHONY: lint lint-fix format format-check typecheck test

# 运行 ruff lint 检查
lint:
	cd backend && ruff check .

# 自动修复 ruff 问题
lint-fix:
	cd backend && ruff check --fix .

# 运行 ruff formatter 检查
format-check:
	cd backend && ruff format --check .

# 自动格式化
format:
	cd backend && ruff format .

# TypeScript 类型检查
typecheck:
	cd frontend && npm run typecheck

# 前端 lint
lint-frontend:
	cd frontend && npm run lint

# 前端格式化
format-frontend:
	cd frontend && npm run format

# 运行测试
test:
	cd backend && pytest

# 完整检查（所有检查）
check: lint lint-frontend typecheck test
	@echo "✓ All checks passed!"
