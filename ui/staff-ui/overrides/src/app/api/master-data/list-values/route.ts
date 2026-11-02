import { NextRequest } from "next/server";
import { proxyToBackend } from "@/app/api/_lib/backend-proxy";

// The active values of one Master Data list with their per-value attributes
// (a vaccine's species and interval_days), from the catalogue. The portal's
// /api/attributes/values reads the older attributes API, which returns no
// value attributes. POST { list_code }.
export async function POST(req: NextRequest) {
	return proxyToBackend({
		req,
		backend: "masterdata",
		targetEndpoint: "/catalogue/get_list_values",
		buildPayload: (body) => ({
			pagination_request: {
				current_page: 1,
				page_size: body.page_size ?? 1000,
				sort_by: "",
				filter_by: "",
				search_text: "",
			},
			request_payload: {
				list_code: body.list_code,
			},
		}),
		transformResponse: (responseBody) => responseBody?.response_payload?.values ?? [],
	});
}
