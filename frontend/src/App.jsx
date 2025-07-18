import { useState } from "react";
import axios from "axios";
import {
  Link as LinkIcon,
  Clock,
  Fingerprint,
  Check,
  X,
  ClipboardCopy,
  ArrowRight,
  Lock,
} from "lucide-react";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

function App() {
  const [url, setUrl] = useState("");
  const [ttlHours, setTtlHours] = useState(24);
  const [maxClicks, setMaxClicks] = useState(1);
  const [short, setShort] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const shorten = async () => {
    setError("");
    setShort("");
    setLoading(true);

    try {
      const res = await axios.post(`${BACKEND_URL}/shorten`, {
        url,
        ttl_hours: ttlHours,
        max_clicks: maxClicks,
      });
      setShort(res.data.short_url);
    } catch (err) {
      const message = err.response?.data?.error || err.message;
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(short);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-800 to-gray-900 px-4 py-12 sm:py-16 text-white">
      <div className="max-w-md mx-auto">
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center mb-3">
            <LinkIcon className="h-10 w-10 text-purple-300 mr-3" />
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-300 to-blue-300">
              SafeLink
            </h1>
          </div>
          <p className="text-purple-200 text-lg">
            Secure, temporary URL shortener
          </p>
        </div>

        {/* Main Card */}
        <div className="bg-gray-800/80 rounded-xl p-6 shadow-xl border border-gray-700">
          <div className="space-y-5">
            {/* URL Input */}
            <div className="space-y-2">
              <label className="flex items-center text-sm font-medium text-gray-300">
                <ArrowRight className="h-4 w-4 mr-1" />
                Destination URL
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/very-long-url..."
                  className="w-full bg-gray-700/60 border border-gray-600 text-white rounded-lg px-4 py-3 pl-10 focus:outline-none focus:ring-2 focus:ring-purple-500 placeholder-gray-400 transition"
                />
                <LinkIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                {url && (
                  <button
                    onClick={() => setUrl("")}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white"
                  >
                    <X className="h-5 w-5" />
                  </button>
                )}
              </div>
            </div>

            {/* Settings Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="flex items-center text-sm font-medium text-gray-300">
                  <Clock className="h-4 w-4 mr-1" />
                  Expires (hours)
                </label>
                <input
                  type="number"
                  value={ttlHours}
                  onChange={(e) => setTtlHours(parseInt(e.target.value))}
                  min="1"
                  className="w-full bg-gray-700/60 border border-gray-600 text-white rounded-lg px-4 py-3 pl-10 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                />
              </div>
              <div className="space-y-2">
                <label className="flex items-center text-sm font-medium text-gray-300">
                  <Fingerprint className="h-4 w-4 mr-1" />
                  Max Clicks
                </label>
                <input
                  type="number"
                  value={maxClicks}
                  onChange={(e) => setMaxClicks(parseInt(e.target.value))}
                  min="1"
                  className="w-full bg-gray-700/60 border border-gray-600 text-white rounded-lg px-4 py-3 pl-10 focus:outline-none focus:ring-2 focus:ring-purple-500 transition"
                />
              </div>
            </div>

            {/* Action Button */}
            <button
              onClick={shorten}
              disabled={loading || !url}
              className={`w-full py-3.5 rounded-lg font-semibold transition-all flex items-center justify-center ${
                loading || !url
                  ? "bg-purple-900 cursor-not-allowed"
                  : "bg-gradient-to-r from-purple-600 to-blue-500 hover:from-purple-700 hover:to-blue-600 shadow-lg"
              }`}
            >
              {loading ? (
                <>
                  <svg
                    className="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                  Creating...
                </>
              ) : (
                "Generate Secure Link"
              )}
            </button>

            {/* Result Section */}
            <div
              className={`min-h-[3rem] transition-opacity duration-300 ${
                short || error ? "opacity-100" : "opacity-0 pointer-events-none"
              }`}
            >
              {short && (
                <div className="mt-4 p-3 bg-gray-700/30 rounded-lg border border-gray-600">
                  <div className="flex items-center justify-between">
                    <a
                      href={short}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-300 hover:text-blue-200 truncate flex-1"
                    >
                      {short}
                    </a>
                    <button
                      onClick={copyToClipboard}
                      className="ml-3 px-2 py-1.5 bg-gray-600 hover:bg-gray-500 rounded text-sm transition flex items-center"
                    >
                      {copied ? (
                        <>
                          <Check className="h-4 w-4 mr-1 text-green-300" />
                          Copied
                        </>
                      ) : (
                        <>
                          <ClipboardCopy className="h-4 w-4 mr-1" />
                          Copy
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {error && (
                <div className="mt-4 p-3 bg-gray-700/30 rounded-lg border border-gray-600 flex items-center text-red-300">
                  <X className="h-5 w-5 mr-2 flex-shrink-0" />
                  {error}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-10 text-center text-gray-400 text-sm">
          <p className="flex items-center justify-center">
            <Lock className="h-4 w-4 mr-1" />
            Links automatically expire after specified time or clicks
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
