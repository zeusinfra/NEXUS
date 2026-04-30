fn main() {
    tonic_build::configure()
        .compile_protos(&["../communication/zeus_core.proto"], &["../communication"])
        .expect("failed to compile protos");
}
