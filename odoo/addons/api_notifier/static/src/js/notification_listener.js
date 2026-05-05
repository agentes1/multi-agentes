import { registry } from "@web/core/registry";

const apiNotifierService = {
    dependencies: ["bus_service", "notification"],
    start(env, { bus_service, notification }) {
        bus_service.addEventListener("notification", ({ detail: notifications }) => {
            for (const item of notifications) {
                if (item.type !== "simple_notification") {
                    continue;
                }

                const payload = item.payload || {};
                notification.add(payload.message || "", {
                    title: payload.title || "Notificacion",
                    type: payload.type || "info",
                    sticky: Boolean(payload.sticky),
                });
            }
        });
    },
};

registry.category("services").add("api_notifier.notification", apiNotifierService);
