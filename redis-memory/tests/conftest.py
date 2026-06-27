"""Shared fixtures for academic team tests."""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_messages():
    return [
        {"role": "user", "content": "研究方向: 物理感知少样本故障诊断"},
        {"role": "assistant", "content": "Decision: Use PINN-based approach"},
        {"role": "user", "content": "Correction: Need few-shot capability too"},
        {"role": "assistant", "content": "→ Skill experiment-bridge deployed"},
        {"role": "assistant", "content": "Key finding: Transformer outperforms CNN by 5%"},
    ]


@pytest.fixture
def sample_papers():
    return [
        {"slug": "paper_a", "title": "Paper A", "authors": ["Author A"],
         "year": 2023, "venue": "VENUE", "tags": ["tag1"],
         "content": "Paper A content", "abstract": "Paper A abstract"},
        {"slug": "paper_b", "title": "Paper B", "authors": ["Author B"],
         "year": 2024, "venue": "VENUE", "tags": ["tag2"],
         "content": "Paper B content", "abstract": "Paper B abstract"},
    ]


@pytest.fixture
def mock_llm(mocker):
    """Mock LLMClient to return fixed responses."""
    mock = mocker.patch("llm_client.LLMClient.complete")
    mock.return_value = "mock response"
    return mock


@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess.Popen for skill calls."""
    mock_proc = mocker.MagicMock()
    mock_proc.stdout = ["line 1\n", "line 2\n"]
    mock_proc.stderr = ""
    mock_proc.returncode = 0
    mocker.patch("subprocess.Popen", return_value=mock_proc)
    return mock_proc
