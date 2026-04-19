/** @type {import('next').NextConfig} */
const webClientUrl = process.env.XOPS_WEB_CLIENT_URL ?? "http://127.0.0.1:5000"

const nextConfig = {
  rewrites: async () => {
    return {
      beforeFiles: [
        {
          source: "/api/:path*",
          destination: `${webClientUrl}/api/:path*`,
        },
      ],
    }
  },
}

export default nextConfig
