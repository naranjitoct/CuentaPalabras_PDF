import sys, platform, tkinter as tk

print("Python:", sys.version)
print("Ejecutable:", sys.executable)
print("SO:", platform.platform())
print("Tk version:", tk.TkVersion)

root = tk.Tk()
root.title("TEST TK FORZADO")
# Tamaño y posición (centrado aproximado)
root.geometry("360x160+300+200")
# Forzar ventana siempre al frente durante 2 segundos
root.attributes("-topmost", True)
root.after(2000, lambda: root.attributes("-topmost", False))

tk.Label(root, text="Deberías ver esta ventana.\nSe cerrará sola en 5 segundos.",
         font=("Segoe UI", 11)).pack(padx=20, pady=20)

# Cerrar solo a los 5 segundos (para que no “pase” desapercibida)
root.after(5000, root.destroy)
root.mainloop()
print("Ventana cerrada correctamente.")
