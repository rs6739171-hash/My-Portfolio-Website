module.exports = function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  res.status(200).json({
    service: "Agentic Automation OS",
    status: "healthy",
    timestamp: new Date().toISOString(),
    cost_mode: "free-tier / dependency-free"
  });
};