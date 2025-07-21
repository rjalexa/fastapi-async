#!/usr/bin/env python3
"""
PDF Extraction Task Testing Utility

This script tests the pdfxtract functionality by:
1. Uploading the il-manifesto-del-31-dicembre-2023.pdf file
2. Monitoring the task until completion
3. Saving the extracted articles as il-manifesto-del-31-dicembre-2023.json
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx


class PdfExtractTester:
    """PDF extraction task tester."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = None

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=60.0
        )  # Longer timeout for PDF processing
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def upload_pdf_for_extraction(
        self, pdf_path: Path, issue_date: Optional[str] = None
    ) -> Optional[str]:
        """Upload PDF file and create extraction task."""
        if not pdf_path.exists():
            print(f"❌ PDF file not found: {pdf_path}")
            return None

        print(f"📄 Uploading PDF: {pdf_path.name}")
        print(f"   File size: {pdf_path.stat().st_size / 1024 / 1024:.2f} MB")

        try:
            # Prepare the multipart form data
            files = {"file": (pdf_path.name, pdf_path.open("rb"), "application/pdf")}

            data = {}
            if issue_date:
                data["issue_date"] = issue_date

            # Upload the PDF
            response = await self.client.post(
                f"{self.base_url}/api/v1/tasks/pdfxtract", files=files, data=data
            )

            if response.status_code == 201:
                result = response.json()
                task_id = result.get("task_id")
                print(f"✅ Task created successfully: {task_id}")
                print(f"   Initial state: {result.get('state')}")
                return task_id
            else:
                print(f"❌ Failed to create task: {response.status_code}")
                print(f"   Error: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Error uploading PDF: {e}")
            return None

    async def monitor_task(
        self, task_id: str, max_wait_time: int = 300
    ) -> Optional[dict]:
        """Monitor task until completion or timeout."""
        print(f"⏳ Monitoring task {task_id}...")

        start_time = time.time()
        last_state = None

        while time.time() - start_time < max_wait_time:
            try:
                response = await self.client.get(
                    f"{self.base_url}/api/v1/tasks/{task_id}"
                )

                if response.status_code == 200:
                    task_data = response.json()
                    current_state = task_data.get("state")

                    # Print state changes
                    if current_state != last_state:
                        elapsed = time.time() - start_time
                        print(f"   State: {current_state} (after {elapsed:.1f}s)")
                        last_state = current_state

                        # Show retry information if available
                        if current_state == "SCHEDULED":
                            retry_count = task_data.get("retry_count", 0)
                            retry_after = task_data.get("retry_after")
                            print(
                                f"   Retry #{retry_count}, scheduled for: {retry_after}"
                            )

                        # Show error information if available
                        if task_data.get("last_error"):
                            error_type = task_data.get("error_type", "Unknown")
                            print(
                                f"   Last error ({error_type}): {task_data['last_error'][:100]}..."
                            )

                    # Check if task is complete
                    if current_state == "COMPLETED":
                        print(
                            f"✅ Task completed successfully in {time.time() - start_time:.1f}s"
                        )
                        return task_data
                    elif current_state == "FAILED":
                        print(f"❌ Task failed after {time.time() - start_time:.1f}s")
                        print(
                            f"   Error: {task_data.get('last_error', 'Unknown error')}"
                        )
                        return task_data
                    elif current_state == "DLQ":
                        print(
                            f"💀 Task moved to dead letter queue after {time.time() - start_time:.1f}s"
                        )
                        print(
                            f"   Error: {task_data.get('last_error', 'Unknown error')}"
                        )
                        return task_data

                else:
                    print(f"❌ Error checking task status: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return None

            except Exception as e:
                print(f"❌ Error monitoring task: {e}")
                return None

            # Wait before next check
            await asyncio.sleep(5)

        print(f"⏰ Task monitoring timed out after {max_wait_time}s")
        return None

    async def save_extraction_result(self, task_data: dict, output_path: Path) -> bool:
        """Save the extraction result to a JSON file."""
        if not task_data or task_data.get("state") != "COMPLETED":
            print("❌ Cannot save result: task not completed successfully")
            return False

        result = task_data.get("result")
        if not result:
            print("❌ No result data found in completed task")
            return False

        try:
            # Parse the result JSON if it's a string
            if isinstance(result, str):
                result_data = json.loads(result)
            else:
                result_data = result

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save the result with pretty formatting
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)

            print(f"💾 Extraction result saved to: {output_path}")

            # Print summary statistics
            if isinstance(result_data, dict):
                pages = result_data.get("pages", [])
                total_pages = len(pages)
                total_articles = sum(len(page.get("articles", [])) for page in pages)
                processed_pages = sum(
                    1 for page in pages if page.get("status") == "processed"
                )
                skipped_pages = total_pages - processed_pages

                print("📊 Extraction Summary:")
                print(f"   Total pages: {total_pages}")
                print(f"   Processed pages: {processed_pages}")
                print(f"   Skipped pages: {skipped_pages}")
                print(f"   Total articles extracted: {total_articles}")

                if total_articles > 0:
                    print(
                        f"   Average articles per processed page: {total_articles/max(processed_pages, 1):.1f}"
                    )

            return True

        except json.JSONDecodeError as e:
            print(f"❌ Error parsing result JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ Error saving result: {e}")
            return False

    async def test_pdf_extraction(
        self,
        pdf_path: Path,
        output_path: Path,
        issue_date: Optional[str] = None,
        max_wait_time: int = 300,
    ) -> bool:
        """Complete PDF extraction test workflow."""
        print("🚀 Starting PDF extraction test")
        print(f"   PDF file: {pdf_path}")
        print(f"   Output file: {output_path}")
        print(f"   Issue date: {issue_date or 'Not specified'}")
        print(f"   Max wait time: {max_wait_time}s")
        print("=" * 60)

        # Step 1: Upload PDF and create task
        task_id = await self.upload_pdf_for_extraction(pdf_path, issue_date)
        if not task_id:
            return False

        # Step 2: Monitor task until completion
        task_data = await self.monitor_task(task_id, max_wait_time)
        if not task_data:
            return False

        # Step 3: Save result if successful
        if task_data.get("state") == "COMPLETED":
            return await self.save_extraction_result(task_data, output_path)
        else:
            print(f"❌ Task did not complete successfully: {task_data.get('state')}")
            return False


async def main():
    """Main function to run PDF extraction test."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test PDF extraction with il-manifesto PDF"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--pdf-path",
        default="docs/il-manifesto-del-31-dicembre-2023.pdf",
        help="Path to the PDF file to process",
    )
    parser.add_argument(
        "--output-path",
        default="docs/il-manifesto-del-31-dicembre-2023.json",
        help="Path for the output JSON file",
    )
    parser.add_argument(
        "--issue-date",
        default="2023-12-31",
        help="Issue date for the newspaper (ISO 8601 format)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum time to wait for task completion (seconds)",
    )

    args = parser.parse_args()

    # Convert paths to Path objects
    pdf_path = Path(args.pdf_path)
    output_path = Path(args.output_path)

    print("PDF Extraction Test")
    print(f"API URL: {args.url}")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print()

    try:
        async with PdfExtractTester(args.url) as tester:
            success = await tester.test_pdf_extraction(
                pdf_path=pdf_path,
                output_path=output_path,
                issue_date=args.issue_date,
                max_wait_time=args.timeout,
            )

        print("=" * 60)
        if success:
            print("🎉 PDF extraction test completed successfully!")
            print(f"📄 Result saved to: {output_path}")
            sys.exit(0)
        else:
            print("❌ PDF extraction test failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
